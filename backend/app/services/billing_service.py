"""Business logic for sales checkout, bill calculation, and atomic inventory deduction."""

import logging
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, TypedDict
from uuid import UUID, uuid4
from collections import defaultdict

from fastapi import HTTPException, status
from sqlalchemy import select, func, and_, or_, text, distinct
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.bill import Bill, BillItem
from app.models.customer import Customer
from app.models.inventory import Inventory
from app.models.payment import Payment
from app.models.product import Product, ProductVariant
from app.models.stock_movement import StockMovement
from app.models.store_settings import StoreSettings
from app.models.user import User
from app.schemas.bill import BillCreate, BillCancelRequest, BillOut, BillItemOut

logger = logging.getLogger("viyon_billing.billing")


class ProcessedLineItem(TypedDict):
    """Internal typed container for validated cart line item snapshot."""
    product_id: UUID
    variant_id: Optional[UUID]
    product_name_snapshot: str
    sku_snapshot: str
    size_snapshot: Optional[str]
    color_snapshot: Optional[str]
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal


class BillingService:
    """Service providing checkout transactions, immutable bill generation, and financial calculation."""

    @staticmethod
    def generate_bill_number(db: Session, prefix: str = "VIYON") -> str:
        """Concurrency-safe bill number generator using PostgreSQL sequence."""
        year = datetime.now(timezone.utc).year
        bind = db.get_bind()
        if bind.dialect.name == "postgresql":
            db.execute(text("CREATE SEQUENCE IF NOT EXISTS bill_number_seq START WITH 1;"))
            seq_val = db.scalar(text("SELECT nextval('bill_number_seq');"))
        else:
            count = db.scalar(select(func.count(Bill.id))) or 0
            seq_val = count + 1
        return f"{prefix}-{year}-{seq_val:06d}"

    @classmethod
    def create_bill(
        cls,
        db: Session,
        bill_in: BillCreate,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> Bill:
        """Create a bill, validate products, atomically deduct inventory with row locks, and record ledger."""
        # 1. Validate Customer if provided
        customer: Optional[Customer] = None
        if bill_in.customer_id is not None:
            customer = db.scalar(select(Customer).where(Customer.id == bill_in.customer_id))
            if not customer:
                raise ValueError(f"Customer with ID '{bill_in.customer_id}' was not found.")

        # 2. Consolidate duplicate cart lines (sum quantities and item discounts)
        consolidated_items: Dict[Tuple[UUID, Optional[UUID]], Dict[str, Decimal]] = defaultdict(
            lambda: {"quantity": Decimal(0), "discount_amount": Decimal("0.00")}
        )
        for item in bill_in.items:
            key = (item.product_id, item.variant_id)
            consolidated_items[key]["quantity"] += Decimal(item.quantity)
            consolidated_items[key]["discount_amount"] += item.discount_amount

        # 3. Sort items deterministically by (product_id, variant_id) to eliminate deadlock risks
        sorted_keys = sorted(
            consolidated_items.keys(),
            key=lambda k: (str(k[0]), str(k[1]) if k[1] else "")
        )

        # 4. Fetch active store configuration for tax computation
        store_settings = db.scalar(
            select(StoreSettings).where(StoreSettings.is_active_config.is_(True))
        )
        tax_enabled = store_settings.tax_enabled if store_settings else False
        tax_rate_percent = (
            store_settings.default_tax_rate if (store_settings and tax_enabled) else Decimal("0.00")
        )

        # 5. Process cart items under pessimistic locks
        line_items_data: List[ProcessedLineItem] = []
        gross_subtotal = Decimal("0.00")
        total_item_discount = Decimal("0.00")
        total_tax = Decimal("0.00")

        try:
            for prod_id, var_id in sorted_keys:
                item_qty = int(consolidated_items[(prod_id, var_id)]["quantity"])
                item_disc = consolidated_items[(prod_id, var_id)]["discount_amount"].quantize(Decimal("0.01"))

                # A. Validate Product
                product = db.scalar(select(Product).where(Product.id == prod_id))
                if not product:
                    raise ValueError(f"Product with ID '{prod_id}' was not found.")

                if product.is_archived:
                    raise ValueError(f"Product '{product.product_name}' is archived and cannot be sold.")

                if not product.is_active:
                    raise ValueError(f"Product '{product.product_name}' is inactive and cannot be sold.")

                # B. Handle Simple vs Variant product rules
                if product.product_type == "SIMPLE":
                    if var_id is not None:
                        raise ValueError(f"Product '{product.product_name}' is a SIMPLE product; variant_id must be null.")
                    if not product.sku:
                        raise ValueError(f"Product '{product.product_name}' lacks a valid SKU and cannot be sold.")

                    unit_price = product.base_price
                    name_snap = product.product_name
                    sku_snap = product.sku
                    size_snap = None
                    color_snap = None

                    # Pessimistic row-lock on inventory
                    inv = db.scalar(
                        select(Inventory)
                        .where(
                            and_(
                                Inventory.product_id == prod_id,
                                Inventory.variant_id.is_(None),
                            )
                        )
                        .with_for_update()
                    )

                else:  # VARIANT
                    if var_id is None:
                        raise ValueError(f"Product '{product.product_name}' is a VARIANT product; variant_id is required.")

                    variant = db.scalar(select(ProductVariant).where(ProductVariant.id == var_id))
                    if not variant or variant.product_id != product.id:
                        raise ValueError(f"Variant with ID '{var_id}' does not belong to product '{product.product_name}'.")

                    if not variant.is_active:
                        raise ValueError(f"Variant '{variant.sku}' is inactive and cannot be sold.")

                    unit_price = variant.price_override if variant.price_override is not None else product.base_price
                    name_snap = product.product_name
                    sku_snap = variant.sku
                    size_snap = variant.size
                    color_snap = variant.color

                    # Pessimistic row-lock on inventory
                    inv = db.scalar(
                        select(Inventory)
                        .where(
                            and_(
                                Inventory.product_id == prod_id,
                                Inventory.variant_id == var_id,
                            )
                        )
                        .with_for_update()
                    )

                # C. Check Inventory & Available Stock
                if not inv:
                    raise ValueError(f"No inventory record found for '{name_snap}' (SKU: {sku_snap}).")

                if inv.quantity < item_qty:
                    raise ValueError(
                        f"Insufficient stock for '{name_snap}' (SKU: {sku_snap}). "
                        f"Available: {inv.quantity}, Requested: {item_qty}."
                    )

                # D. Deduct Inventory Stock
                inv.quantity -= item_qty

                # E. Calculate item financials
                unit_price_dec = Decimal(str(unit_price)).quantize(Decimal("0.01"))
                item_gross = (unit_price_dec * Decimal(item_qty)).quantize(Decimal("0.01"))

                if item_disc > item_gross:
                    raise ValueError(
                        f"Item discount ({item_disc}) cannot exceed item gross total ({item_gross}) for '{name_snap}'."
                    )

                item_net = item_gross - item_disc
                item_tax = Decimal("0.00")
                if tax_enabled and tax_rate_percent > Decimal("0.00"):
                    item_tax = (item_net * (tax_rate_percent / Decimal("100.00"))).quantize(Decimal("0.01"))

                line_total = item_net + item_tax

                gross_subtotal += item_gross
                total_item_discount += item_disc
                total_tax += item_tax

                line_items_data.append({
                    "product_id": prod_id,
                    "variant_id": var_id,
                    "product_name_snapshot": name_snap,
                    "sku_snapshot": sku_snap,
                    "size_snapshot": size_snap,
                    "color_snapshot": color_snap,
                    "quantity": item_qty,
                    "unit_price": unit_price_dec,
                    "discount_amount": item_disc,
                    "tax_amount": item_tax,
                    "line_total": line_total,
                })

            # 6. Apply bill-level discount and compute final invoice total
            bill_disc = bill_in.discount_amount.quantize(Decimal("0.01"))
            total_discount = total_item_discount + bill_disc

            if total_discount > gross_subtotal:
                raise ValueError(
                    f"Total discount ({total_discount}) cannot exceed bill subtotal ({gross_subtotal})."
                )

            final_total = gross_subtotal - total_discount + total_tax
            if final_total < Decimal("0.00"):
                raise ValueError("Final bill total cannot be negative.")

            # 7. Generate unique bill number
            store_prefix = store_settings.store_name.strip().upper() if store_settings else "VIYON"
            bill_number = cls.generate_bill_number(db, prefix=store_prefix)

            # 8. Create Bill Header
            bill = Bill(
                id=uuid4(),
                bill_number=bill_number,
                customer_id=bill_in.customer_id,
                staff_user_id=current_user.id,
                bill_date=datetime.now(timezone.utc),
                subtotal=gross_subtotal,
                discount_amount=total_discount,
                tax_amount=total_tax,
                total_amount=final_total,
                amount_paid=Decimal("0.00"),
                balance_amount=final_total,
                payment_status="PENDING",
                bill_status="COMPLETED",
                notes=bill_in.notes.strip() if bill_in.notes else None,
            )
            db.add(bill)
            db.flush()

            # 9. Create Bill Items and Stock Movements
            for item_data in line_items_data:
                sold_qty = item_data["quantity"]
                bill_item = BillItem(
                    id=uuid4(),
                    bill_id=bill.id,
                    product_id=item_data["product_id"],
                    variant_id=item_data["variant_id"],
                    product_name_snapshot=item_data["product_name_snapshot"],
                    sku_snapshot=item_data["sku_snapshot"],
                    size_snapshot=item_data["size_snapshot"],
                    color_snapshot=item_data["color_snapshot"],
                    quantity=sold_qty,
                    unit_price=item_data["unit_price"],
                    discount_amount=item_data["discount_amount"],
                    tax_amount=item_data["tax_amount"],
                    line_total=item_data["line_total"],
                )
                db.add(bill_item)

                movement = StockMovement(
                    id=uuid4(),
                    product_id=item_data["product_id"],
                    variant_id=item_data["variant_id"],
                    movement_type="SALE",
                    quantity_change=-sold_qty,
                    reference_type="BILL",
                    reference_id=bill.id,
                    notes=f"Sale on Bill {bill.bill_number}",
                    created_by_user_id=current_user.id,
                )
                db.add(movement)

            # 10. Process atomic checkout payments if provided
            now_utc = datetime.now(timezone.utc)
            if bill_in.payments:
                total_payment_sum = Decimal("0.00")
                confirmed_sum = Decimal("0.00")

                for p_in in bill_in.payments:
                    p_amount = p_in.amount.quantize(Decimal("0.01"))
                    if p_amount <= Decimal("0.00"):
                        raise ValueError("Payment amount must be greater than zero.")
                    total_payment_sum += p_amount

                    cleaned_ref = p_in.transaction_reference
                    if cleaned_ref:
                        duplicate = db.scalar(
                            select(Payment).where(
                                Payment.transaction_reference == cleaned_ref,
                                Payment.payment_status.in_(["CONFIRMED", "PENDING"]),
                            )
                        )
                        if duplicate:
                            raise ValueError(
                                f"Transaction reference '{cleaned_ref}' is already associated with existing payment ID '{duplicate.id}'."
                            )

                    # All counter payments (CASH, UPI, and SPLIT) are immediately confirmed as PAID
                    p_status = "CONFIRMED"
                    conf_by = current_user.id
                    conf_at = now_utc

                    payment = Payment(
                        id=uuid4(),
                        bill_id=bill.id,
                        payment_method=p_in.payment_method,
                        amount=p_amount,
                        payment_status=p_status,
                        transaction_reference=cleaned_ref,
                        received_by_user_id=current_user.id,
                        received_at=now_utc,
                        confirmed_by_user_id=conf_by,
                        confirmed_at=conf_at,
                        notes=p_in.notes.strip() if p_in.notes else None,
                        created_at=now_utc,
                        updated_at=now_utc,
                    )
                    db.add(payment)

                    confirmed_sum += p_amount

                    audit = AuditLog(
                        id=uuid4(),
                        user_id=current_user.id,
                        action=f"PAYMENT_RECORDED_{p_status}",
                        entity_type="PAYMENT",
                        entity_id=payment.id,
                        new_values={
                            "bill_id": str(bill.id),
                            "bill_number": bill.bill_number,
                            "amount": str(p_amount),
                            "payment_method": payment.payment_method,
                            "payment_status": payment.payment_status,
                            "transaction_reference": payment.transaction_reference,
                            "is_confirmed": True,
                        },
                        ip_address=ip_address,
                        created_at=now_utc,
                    )
                    db.add(audit)

                if total_payment_sum != final_total:
                    raise ValueError(
                        f"Total payment amount (Rs. {total_payment_sum}) must match bill total (Rs. {final_total})."
                    )

                # Update bill payment totals
                bill.amount_paid = confirmed_sum
                bill.balance_amount = (final_total - confirmed_sum).quantize(Decimal("0.01"))
                if bill.balance_amount == Decimal("0.00"):
                    bill.payment_status = "PAID"
                elif confirmed_sum > Decimal("0.00"):
                    bill.payment_status = "PARTIALLY_PAID"
                else:
                    bill.payment_status = "PENDING"
                bill.updated_at = now_utc

            # 11. Commit entire atomic checkout transaction
            db.commit()
            return cls.get_bill_by_id(db, bill.id)  # type: ignore

        except Exception:
            db.rollback()
            raise

    @classmethod
    def get_bill_by_id(cls, db: Session, bill_id: UUID) -> Optional[Bill]:
        """Fetch bill with customer, staff, line items, and payments loaded."""
        return db.scalar(
            select(Bill)
            .where(Bill.id == bill_id)
            .options(
                joinedload(Bill.customer),
                joinedload(Bill.staff_user),
                joinedload(Bill.cancelled_by_user),
                joinedload(Bill.items),
                joinedload(Bill.payments),
            )
        )

    @classmethod
    def list_bills(
        cls,
        db: Session,
        search: Optional[str] = None,
        bill_number: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        staff_user_id: Optional[UUID] = None,
        bill_status: Optional[str] = None,
        payment_status: Optional[str] = None,
        payment_method: Optional[str] = None,
        is_cancelled: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        sort_order: str = "desc",
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[BillOut], int, int, int, int, int]:
        """Query bills with filtering, search, sorting, and dual pagination formats.

        Returns:
            Tuple[items, total, effective_limit, effective_offset, page, total_pages]
        """
        # Determine pagination parameters
        if page is not None and page_size is not None:
            eff_limit = max(1, min(page_size, 100))
            eff_page = max(1, page)
            eff_offset = (eff_page - 1) * eff_limit
        else:
            eff_limit = max(1, min(limit, 100))
            eff_offset = max(0, offset)
            eff_page = (eff_offset // eff_limit) + 1

        query = (
            select(Bill)
            .options(
                joinedload(Bill.customer),
                joinedload(Bill.staff_user),
                joinedload(Bill.cancelled_by_user),
                joinedload(Bill.items),
                joinedload(Bill.payments),
            )
        )
        count_query = select(func.count(distinct(Bill.id)))

        # Joins if required by filters
        if customer_name or customer_phone:
            query = query.outerjoin(Customer, Bill.customer_id == Customer.id)
            count_query = count_query.outerjoin(Customer, Bill.customer_id == Customer.id)

        if payment_method:
            query = query.outerjoin(Payment, Bill.id == Payment.bill_id)
            count_query = count_query.outerjoin(Payment, Bill.id == Payment.bill_id)

        filters = []

        if customer_id is not None:
            filters.append(Bill.customer_id == customer_id)
        if staff_user_id is not None:
            filters.append(Bill.staff_user_id == staff_user_id)
        if bill_status:
            filters.append(Bill.bill_status == bill_status.strip().upper())
        if payment_status:
            filters.append(Bill.payment_status == payment_status.strip().upper())
        if start_date is not None:
            filters.append(Bill.bill_date >= start_date)
        if end_date is not None:
            filters.append(Bill.bill_date <= end_date)

        if is_cancelled is not None:
            if is_cancelled:
                filters.append(Bill.bill_status == "CANCELLED")
            else:
                filters.append(Bill.bill_status != "CANCELLED")

        if bill_number:
            filters.append(Bill.bill_number.ilike(f"%{bill_number.strip()}%"))
        elif search:
            filters.append(Bill.bill_number.ilike(f"%{search.strip()}%"))

        if customer_name:
            filters.append(Customer.customer_name.ilike(f"%{customer_name.strip()}%"))
        if customer_phone:
            filters.append(Customer.phone.ilike(f"%{customer_phone.strip()}%"))

        if payment_method:
            filters.append(Payment.payment_method == payment_method.strip().upper())

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        total = db.scalar(count_query) or 0
        total_pages = max(1, math.ceil(total / eff_limit)) if total > 0 else 1

        # Sorting
        if sort_order.lower() == "asc":
            query = query.order_by(Bill.bill_date.asc())
        else:
            query = query.order_by(Bill.bill_date.desc())

        query = query.limit(eff_limit).offset(eff_offset)
        bills = db.scalars(query).unique().all()

        results = [cls._build_bill_out(b) for b in bills]
        return results, total, eff_limit, eff_offset, eff_page, total_pages

    @classmethod
    def cancel_bill(
        cls,
        db: Session,
        bill_id: UUID,
        cancel_in: BillCancelRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> BillOut:
        """Cancel a completed bill, atomically restore inventory, reject pending payments, and log audit."""
        # 1. Pessimistic lock on Bill row directly (never use joinedload with for_update)
        bill = db.scalar(
            select(Bill)
            .where(Bill.id == bill_id)
            .with_for_update()
        )
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bill with ID '{bill_id}' was not found.",
            )

        if bill.bill_status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bill '{bill.bill_number}' has already been cancelled.",
            )

        if bill.bill_status == "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot cancel a DRAFT bill.",
            )

        clean_reason = cancel_in.reason.strip()
        now_utc = datetime.now(timezone.utc)

        # 2. Fetch bill line items and sort deterministically to eliminate deadlocks
        bill_items = list(
            db.scalars(
                select(BillItem)
                .where(BillItem.bill_id == bill.id)
            ).all()
        )
        sorted_items = sorted(
            bill_items,
            key=lambda it: (str(it.product_id or ""), str(it.variant_id or "")),
        )

        restored_items_data: List[Dict[str, Any]] = []

        # 3. Restore inventory and write StockMovement for each line item
        for item in sorted_items:
            inv_query = select(Inventory).where(Inventory.product_id == item.product_id)
            if item.variant_id is not None:
                inv_query = inv_query.where(Inventory.variant_id == item.variant_id)
            else:
                inv_query = inv_query.where(Inventory.variant_id.is_(None))

            inv = db.scalar(inv_query.with_for_update())
            if not inv:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Inventory record missing for item '{item.product_name_snapshot}' (SKU: {item.sku_snapshot}).",
                )

            inv.quantity += item.quantity

            movement = StockMovement(
                id=uuid4(),
                product_id=item.product_id,
                variant_id=item.variant_id,
                movement_type="CANCELLATION",
                quantity_change=item.quantity,  # positive quantity restoration
                reference_type="BILL_CANCELLATION",
                reference_id=bill.id,
                notes=f"Restored {item.quantity} units from cancelled bill {bill.bill_number}: {clean_reason}",
                created_by_user_id=current_user.id,
                created_at=now_utc,
            )
            db.add(movement)

            restored_items_data.append({
                "product_name": item.product_name_snapshot,
                "sku": item.sku_snapshot,
                "quantity": item.quantity,
                "new_inventory_qty": inv.quantity,
            })

        # 4. Handle Payments: preserve confirmed, reject pending
        payments = list(
            db.scalars(
                select(Payment)
                .where(Payment.bill_id == bill.id)
                .with_for_update()
            ).all()
        )

        confirmed_payments_sum = Decimal("0.00")
        for p in payments:
            if p.payment_status == "CONFIRMED":
                confirmed_payments_sum += p.amount
            elif p.payment_status == "PENDING":
                p.payment_status = "REJECTED"
                p.rejection_reason = f"Bill {bill.bill_number} cancelled: {clean_reason}"
                p.confirmed_by_user_id = current_user.id
                p.updated_at = now_utc

        # 5. Update Bill Cancellation metadata
        old_status = bill.bill_status
        bill.bill_status = "CANCELLED"
        bill.cancelled_at = now_utc
        bill.cancelled_by_user_id = current_user.id
        bill.cancellation_reason = clean_reason
        bill.updated_at = now_utc

        # 6. Record Audit Log
        audit = AuditLog(
            id=uuid4(),
            user_id=current_user.id,
            action="BILL_CANCELLED",
            entity_type="BILL",
            entity_id=bill.id,
            old_values={
                "bill_status": old_status,
                "payment_status": bill.payment_status,
            },
            new_values={
                "bill_number": bill.bill_number,
                "bill_status": "CANCELLED",
                "cancelled_by_user_id": str(current_user.id),
                "cancellation_reason": clean_reason,
                "cancelled_at": now_utc.isoformat(),
                "restored_items": restored_items_data,
                "confirmed_payment_amount": str(confirmed_payments_sum),
                "refund_review_amount": str(confirmed_payments_sum),
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)

        # 7. Commit transaction
        db.commit()

        logger.info(
            f"Bill cancelled: ID={bill.id} Number={bill.bill_number} By={current_user.email} "
            f"RestoredItems={len(restored_items_data)} ConfirmedPayments={confirmed_payments_sum}"
        )

        updated_bill = cls.get_bill_by_id(db, bill.id)
        if not updated_bill:
            return cls._build_bill_out(bill)
        return cls._build_bill_out(updated_bill)

    @classmethod
    def get_bill_items(cls, db: Session, bill_id: UUID) -> List[BillItemOut]:
        """Retrieve snapshot line items for a bill."""
        bill = cls.get_bill_by_id(db, bill_id)
        if not bill:
            return []
        return [
            BillItemOut(
                id=item.id,
                bill_id=item.bill_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                product_name_snapshot=item.product_name_snapshot,
                sku_snapshot=item.sku_snapshot,
                size_snapshot=item.size_snapshot,
                color_snapshot=item.color_snapshot,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_amount=item.discount_amount,
                tax_amount=item.tax_amount,
                line_total=item.line_total,
                created_at=item.created_at,
            )
            for item in bill.items
        ]

    # --------------------------------------------------------------------------
    # Helper Serialization
    # --------------------------------------------------------------------------
    @staticmethod
    def _build_bill_out(bill: Bill) -> BillOut:
        """Convert Bill ORM entity into public BillOut response schema."""
        items_out = [
            BillItemOut(
                id=item.id,
                bill_id=item.bill_id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                product_name_snapshot=item.product_name_snapshot,
                sku_snapshot=item.sku_snapshot,
                size_snapshot=item.size_snapshot,
                color_snapshot=item.color_snapshot,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_amount=item.discount_amount,
                tax_amount=item.tax_amount,
                line_total=item.line_total,
                created_at=item.created_at,
            )
            for item in bill.items
        ]

        refund_review = None
        if bill.bill_status == "CANCELLED":
            refund_review = sum(
                (p.amount for p in bill.payments if p.payment_status == "CONFIRMED"),
                Decimal("0.00"),
            )

        return BillOut(
            id=bill.id,
            bill_number=bill.bill_number,
            customer_id=bill.customer_id,
            customer_name=bill.customer.customer_name if bill.customer else None,
            customer_phone=bill.customer.phone if bill.customer else None,
            staff_user_id=bill.staff_user_id,
            staff_name=bill.staff_user.full_name if bill.staff_user else None,
            bill_date=bill.bill_date,
            subtotal=bill.subtotal,
            discount_amount=bill.discount_amount,
            tax_amount=bill.tax_amount,
            total_amount=bill.total_amount,
            amount_paid=bill.amount_paid,
            balance_amount=bill.balance_amount,
            payment_status=bill.payment_status,
            bill_status=bill.bill_status,
            notes=bill.notes,
            items=items_out,
            cancelled_at=bill.cancelled_at,
            cancelled_by_user_id=bill.cancelled_by_user_id,
            cancelled_by_name=bill.cancelled_by_user.full_name if bill.cancelled_by_user else None,
            cancellation_reason=bill.cancellation_reason,
            refund_review_amount=refund_review,
            created_at=bill.created_at,
            updated_at=bill.updated_at,
        )
