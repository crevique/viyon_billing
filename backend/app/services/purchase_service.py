"""Service layer for Phase 5.4: Supplier & Purchase Management System.
Handles atomic transactional PO workflows, Goods Receiving with row locks and stock increment,
Supplier Payments with pending/confirmed state machines, and financial liability summaries.
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, distinct, func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from app.models.audit_log import AuditLog
from app.models.inventory import Inventory
from app.models.product import Product, ProductVariant
from app.models.purchase import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierPayment,
)
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.purchase import (
    GoodsReceiptCreate,
    GoodsReceiptItemOut,
    GoodsReceiptOut,
    PurchaseOrderCancelRequest,
    PurchaseOrderCreate,
    PurchaseOrderItemOut,
    PurchaseOrderOut,
    PurchaseOrderUpdate,
    PurchaseSummaryOut,
    SupplierCreate,
    SupplierOut,
    SupplierPaymentConfirmRequest,
    SupplierPaymentCreate,
    SupplierPaymentOut,
    SupplierPaymentRejectRequest,
    SupplierUpdate,
)

logger = logging.getLogger("viyon_billing.purchase")


class PurchaseService:
    """Core domain service for Supplier and Purchase Order operations."""

    # ==========================================================================
    # Sequence Generators
    # ==========================================================================
    @staticmethod
    def generate_po_number(db: Session, prefix: str = "VIYON-PO") -> str:
        """Concurrency-safe Purchase Order number generator."""
        year = datetime.now(timezone.utc).year
        bind = db.get_bind()
        if bind.dialect.name == "postgresql":
            db.execute(text("CREATE SEQUENCE IF NOT EXISTS po_number_seq START WITH 1;"))
            seq_val = db.scalar(text("SELECT nextval('po_number_seq');"))
        else:
            count = db.scalar(select(func.count(PurchaseOrder.id))) or 0
            seq_val = count + 1
        return f"{prefix}-{year}-{seq_val:06d}"

    @staticmethod
    def generate_grn_number(db: Session, prefix: str = "VIYON-GRN") -> str:
        """Concurrency-safe Goods Receipt Note number generator."""
        year = datetime.now(timezone.utc).year
        bind = db.get_bind()
        if bind.dialect.name == "postgresql":
            db.execute(text("CREATE SEQUENCE IF NOT EXISTS grn_number_seq START WITH 1;"))
            seq_val = db.scalar(text("SELECT nextval('grn_number_seq');"))
        else:
            count = db.scalar(select(func.count(GoodsReceipt.id))) or 0
            seq_val = count + 1
        return f"{prefix}-{year}-{seq_val:06d}"

    @staticmethod
    def generate_payment_number(db: Session, prefix: str = "VIYON-SP") -> str:
        """Concurrency-safe Supplier Payment number generator."""
        year = datetime.now(timezone.utc).year
        bind = db.get_bind()
        if bind.dialect.name == "postgresql":
            db.execute(text("CREATE SEQUENCE IF NOT EXISTS supplier_payment_seq START WITH 1;"))
            seq_val = db.scalar(text("SELECT nextval('supplier_payment_seq');"))
        else:
            count = db.scalar(select(func.count(SupplierPayment.id))) or 0
            seq_val = count + 1
        return f"{prefix}-{year}-{seq_val:06d}"

    # ==========================================================================
    # 1. Supplier Operations
    # ==========================================================================
    @classmethod
    def create_supplier(cls, db: Session, supplier_in: SupplierCreate) -> Supplier:
        """Create a new active supplier with unique company name validation."""
        # Check duplicate company name
        existing = db.scalar(
            select(Supplier).where(
                func.lower(Supplier.company_name) == supplier_in.company_name.strip().lower()
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Supplier with company name '{supplier_in.company_name.strip()}' already exists.",
            )

        supplier = Supplier(
            company_name=supplier_in.company_name.strip(),
            contact_person=supplier_in.contact_person.strip() if supplier_in.contact_person else None,
            phone=supplier_in.phone.strip(),
            alternate_phone=supplier_in.alternate_phone.strip() if supplier_in.alternate_phone else None,
            email=supplier_in.email.strip().lower() if supplier_in.email else None,
            gstin=supplier_in.gstin.strip().upper() if supplier_in.gstin else None,
            address=supplier_in.address.strip() if supplier_in.address else None,
            city=supplier_in.city.strip() if supplier_in.city else None,
            state=supplier_in.state.strip() if supplier_in.state else None,
            pincode=supplier_in.pincode.strip() if supplier_in.pincode else None,
            notes=supplier_in.notes.strip() if supplier_in.notes else None,
            is_active=True,
        )
        db.add(supplier)
        db.commit()
        db.refresh(supplier)
        logger.info("Supplier created: %s (ID: %s)", supplier.company_name, supplier.id)
        return supplier

    @classmethod
    def update_supplier(cls, db: Session, supplier_id: UUID, supplier_in: SupplierUpdate) -> Supplier:
        """Update supplier details."""
        supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id))
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier with ID '{supplier_id}' not found.",
            )

        if supplier_in.company_name is not None and supplier_in.company_name.strip():
            new_name = supplier_in.company_name.strip()
            if new_name.lower() != supplier.company_name.lower():
                dup = db.scalar(
                    select(Supplier).where(
                        and_(
                            func.lower(Supplier.company_name) == new_name.lower(),
                            Supplier.id != supplier_id,
                        )
                    )
                )
                if dup:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Another supplier with company name '{new_name}' already exists.",
                    )
            supplier.company_name = new_name

        if supplier_in.contact_person is not None:
            supplier.contact_person = supplier_in.contact_person.strip() or None
        if supplier_in.phone is not None:
            supplier.phone = supplier_in.phone.strip()
        if supplier_in.alternate_phone is not None:
            supplier.alternate_phone = supplier_in.alternate_phone.strip() or None
        if supplier_in.email is not None:
            supplier.email = supplier_in.email.strip().lower() or None
        if supplier_in.gstin is not None:
            supplier.gstin = supplier_in.gstin.strip().upper() or None
        if supplier_in.address is not None:
            supplier.address = supplier_in.address.strip() or None
        if supplier_in.city is not None:
            supplier.city = supplier_in.city.strip() or None
        if supplier_in.state is not None:
            supplier.state = supplier_in.state.strip() or None
        if supplier_in.pincode is not None:
            supplier.pincode = supplier_in.pincode.strip() or None
        if supplier_in.notes is not None:
            supplier.notes = supplier_in.notes.strip() or None
        if supplier_in.is_active is not None:
            supplier.is_active = supplier_in.is_active

        db.commit()
        db.refresh(supplier)
        logger.info("Supplier updated: %s", supplier.company_name)
        return supplier

    @classmethod
    def set_supplier_status(cls, db: Session, supplier_id: UUID, is_active: bool) -> Supplier:
        """Activate or deactivate a supplier."""
        supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id))
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier with ID '{supplier_id}' not found.",
            )
        supplier.is_active = is_active
        db.commit()
        db.refresh(supplier)
        logger.info("Supplier %s status set to is_active=%s", supplier.company_name, is_active)
        return supplier

    @classmethod
    def _compute_supplier_financials(cls, db: Session, supplier_id: UUID) -> Dict[str, Any]:
        """Compute aggregated purchase totals and outstanding balance for a supplier."""
        # Total Purchases: sum of grand_total of non-cancelled POs
        total_purchases = (
            db.scalar(
                select(func.coalesce(func.sum(PurchaseOrder.grand_total), Decimal("0.00"))).where(
                    and_(
                        PurchaseOrder.supplier_id == supplier_id,
                        PurchaseOrder.status != "CANCELLED",
                    )
                )
            )
            or Decimal("0.00")
        )

        # Total Goods Received Value: sum of accepted items * unit_cost
        grn_val_stmt = (
            select(
                func.coalesce(
                    func.sum(GoodsReceiptItem.quantity_accepted * PurchaseOrderItem.unit_cost),
                    Decimal("0.00"),
                )
            )
            .join(GoodsReceipt, GoodsReceiptItem.goods_receipt_id == GoodsReceipt.id)
            .join(PurchaseOrderItem, GoodsReceiptItem.purchase_order_item_id == PurchaseOrderItem.id)
            .where(GoodsReceipt.supplier_id == supplier_id)
        )
        total_goods_received_value = db.scalar(grn_val_stmt) or Decimal("0.00")

        # Total Confirmed Payments made to this supplier
        total_paid = (
            db.scalar(
                select(func.coalesce(func.sum(SupplierPayment.amount), Decimal("0.00"))).where(
                    and_(
                        SupplierPayment.supplier_id == supplier_id,
                        SupplierPayment.status == "CONFIRMED",
                    )
                )
            )
            or Decimal("0.00")
        )

        outstanding_balance = max(Decimal("0.00"), total_purchases - total_paid)

        # Last purchase date
        last_purchase_date = db.scalar(
            select(func.max(PurchaseOrder.po_date)).where(
                and_(
                    PurchaseOrder.supplier_id == supplier_id,
                    PurchaseOrder.status != "CANCELLED",
                )
            )
        )

        return {
            "total_purchases": total_purchases,
            "total_goods_received_value": total_goods_received_value,
            "total_paid": total_paid,
            "outstanding_balance": outstanding_balance,
            "last_purchase_date": last_purchase_date,
        }

    @classmethod
    def get_supplier_out(cls, db: Session, supplier: Supplier) -> SupplierOut:
        """Convert Supplier model to SupplierOut with live financial calculations."""
        fin = cls._compute_supplier_financials(db, supplier.id)
        return SupplierOut(
            id=supplier.id,
            company_name=supplier.company_name,
            contact_person=supplier.contact_person,
            phone=supplier.phone,
            alternate_phone=supplier.alternate_phone,
            email=supplier.email,
            gstin=supplier.gstin,
            address=supplier.address,
            city=supplier.city,
            state=supplier.state,
            pincode=supplier.pincode,
            notes=supplier.notes,
            is_active=supplier.is_active,
            total_purchases=fin["total_purchases"],
            total_goods_received_value=fin["total_goods_received_value"],
            total_paid=fin["total_paid"],
            outstanding_balance=fin["outstanding_balance"],
            last_purchase_date=fin["last_purchase_date"],
            created_at=supplier.created_at,
            updated_at=supplier.updated_at,
        )

    @classmethod
    def get_supplier_by_id(cls, db: Session, supplier_id: UUID) -> SupplierOut:
        """Get single supplier by ID."""
        supplier = db.scalar(select(Supplier).where(Supplier.id == supplier_id))
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier with ID '{supplier_id}' not found.",
            )
        return cls.get_supplier_out(db, supplier)

    @classmethod
    def list_suppliers(
        cls,
        db: Session,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[SupplierOut], int]:
        """List suppliers with filtering, searching, and pagination."""
        query = select(Supplier)
        filters = []
        if is_active is not None:
            filters.append(Supplier.is_active == is_active)
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(Supplier.company_name).ilike(term),
                    func.lower(Supplier.contact_person).ilike(term),
                    Supplier.phone.ilike(term),
                    func.lower(Supplier.email).ilike(term),
                    Supplier.gstin.ilike(term),
                )
            )

        if filters:
            query = query.where(and_(*filters))

        count_stmt = select(func.count(Supplier.id))
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = db.scalar(count_stmt) or 0

        query = query.order_by(Supplier.company_name.asc()).limit(limit).offset(offset)
        suppliers = db.scalars(query).all()

        results = [cls.get_supplier_out(db, s) for s in suppliers]
        return results, total

    # ==========================================================================
    # 2. Purchase Order Operations
    # ==========================================================================
    @classmethod
    def create_purchase_order(
        cls,
        db: Session,
        po_in: PurchaseOrderCreate,
        current_user: User,
    ) -> PurchaseOrder:
        """Create a new Purchase Order in DRAFT status without modifying inventory."""
        # 1. Validate Supplier
        supplier = db.scalar(select(Supplier).where(Supplier.id == po_in.supplier_id))
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier with ID '{po_in.supplier_id}' not found.",
            )
        if not supplier.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot create purchase order: Supplier '{supplier.company_name}' is inactive.",
            )

        po_id = uuid.uuid4()
        po_number = cls.generate_po_number(db)

        # 2. Validate Items and Calculate Financials
        po_items: List[PurchaseOrderItem] = []
        subtotal = Decimal("0.00")
        total_discount = Decimal("0.00")
        total_tax = Decimal("0.00")
        grand_total = Decimal("0.00")

        for item_in in po_in.items:
            product = db.scalar(select(Product).where(Product.id == item_in.product_id))
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with ID '{item_in.product_id}' not found.",
                )
            if product.is_archived:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product '{product.product_name}' is archived and cannot be ordered.",
                )

            # Validate variant compatibility
            if product.product_type == "VARIANT":
                if not item_in.variant_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Product '{product.product_name}' is a VARIANT product; variant_id is required.",
                    )
                variant = db.scalar(
                    select(ProductVariant).where(
                        and_(
                            ProductVariant.id == item_in.variant_id,
                            ProductVariant.product_id == item_in.product_id,
                        )
                    )
                )
                if not variant:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Variant '{item_in.variant_id}' does not belong to product '{product.product_name}'.",
                    )
            else:
                if item_in.variant_id is not None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Product '{product.product_name}' is a SIMPLE product; variant_id must be null.",
                    )

            # Financial calculations per line
            base_amount = Decimal(item_in.quantity_ordered) * Decimal(item_in.unit_cost)
            item_discount = base_amount * (Decimal(item_in.discount_percent) / Decimal("100"))
            after_discount = base_amount - item_discount
            item_tax = after_discount * (Decimal(item_in.tax_percent) / Decimal("100"))
            line_total = after_discount + item_tax

            subtotal += base_amount
            total_discount += item_discount
            total_tax += item_tax
            grand_total += line_total

            po_item = PurchaseOrderItem(
                id=uuid.uuid4(),
                purchase_order_id=po_id,
                product_id=item_in.product_id,
                variant_id=item_in.variant_id,
                quantity_ordered=item_in.quantity_ordered,
                quantity_received=0,
                unit_cost=item_in.unit_cost,
                discount_percent=item_in.discount_percent,
                tax_percent=item_in.tax_percent,
                line_total=line_total.quantize(Decimal("0.01")),
            )
            po_items.append(po_item)

        # 3. Create PO record
        po = PurchaseOrder(
            id=po_id,
            po_number=po_number,
            supplier_id=po_in.supplier_id,
            expected_delivery_date=po_in.expected_delivery_date,
            status="DRAFT",
            subtotal=subtotal.quantize(Decimal("0.01")),
            discount_amount=total_discount.quantize(Decimal("0.01")),
            tax_amount=total_tax.quantize(Decimal("0.01")),
            grand_total=grand_total.quantize(Decimal("0.01")),
            notes=po_in.notes.strip() if po_in.notes else None,
            created_by_user_id=current_user.id,
            items=po_items,
        )
        db.add(po)
        db.commit()
        db.refresh(po)
        logger.info("Purchase Order created: %s (Total: Rs. %s)", po.po_number, po.grand_total)
        return po

    @classmethod
    def update_purchase_order(
        cls,
        db: Session,
        po_id: UUID,
        po_update: PurchaseOrderUpdate,
        current_user: User,
    ) -> PurchaseOrder:
        """Edit an existing DRAFT purchase order."""
        po = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .options(joinedload(PurchaseOrder.items))
        )
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order with ID '{po_id}' not found.",
            )
        if po.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit purchase order '{po.po_number}': Status is '{po.status}'. Only DRAFT orders can be modified.",
            )

        if po_update.expected_delivery_date is not None:
            po.expected_delivery_date = po_update.expected_delivery_date
        if po_update.notes is not None:
            po.notes = po_update.notes.strip() or None

        if po_update.items is not None and len(po_update.items) > 0:
            # Delete old items and recalculate
            for old_item in list(po.items):
                db.delete(old_item)

            subtotal = Decimal("0.00")
            total_discount = Decimal("0.00")
            total_tax = Decimal("0.00")
            grand_total = Decimal("0.00")
            new_items = []

            for item_in in po_update.items:
                product = db.scalar(select(Product).where(Product.id == item_in.product_id))
                if not product or product.is_archived:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid product ID '{item_in.product_id}'.",
                    )
                base_amount = Decimal(item_in.quantity_ordered) * Decimal(item_in.unit_cost)
                item_discount = base_amount * (Decimal(item_in.discount_percent) / Decimal("100"))
                after_discount = base_amount - item_discount
                item_tax = after_discount * (Decimal(item_in.tax_percent) / Decimal("100"))
                line_total = after_discount + item_tax

                subtotal += base_amount
                total_discount += item_discount
                total_tax += item_tax
                grand_total += line_total

                new_item = PurchaseOrderItem(
                    id=uuid.uuid4(),
                    purchase_order_id=po.id,
                    product_id=item_in.product_id,
                    variant_id=item_in.variant_id,
                    quantity_ordered=item_in.quantity_ordered,
                    quantity_received=0,
                    unit_cost=item_in.unit_cost,
                    discount_percent=item_in.discount_percent,
                    tax_percent=item_in.tax_percent,
                    line_total=line_total.quantize(Decimal("0.01")),
                )
                new_items.append(new_item)

            po.items = new_items
            po.subtotal = subtotal.quantize(Decimal("0.01"))
            po.discount_amount = total_discount.quantize(Decimal("0.01"))
            po.tax_amount = total_tax.quantize(Decimal("0.01"))
            po.grand_total = grand_total.quantize(Decimal("0.01"))

        db.commit()
        db.refresh(po)
        logger.info("Purchase Order updated: %s", po.po_number)
        return po

    @classmethod
    def place_purchase_order(cls, db: Session, po_id: UUID, current_user: User) -> PurchaseOrder:
        """Place purchase order with supplier (Transition from DRAFT to ORDERED). Does NOT increase stock."""
        po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == po_id))
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order with ID '{po_id}' not found.",
            )
        if po.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase order '{po.po_number}' cannot be placed: Current status is '{po.status}'.",
            )

        po.status = "ORDERED"
        db.commit()
        db.refresh(po)
        logger.info("Purchase Order placed: %s -> ORDERED", po.po_number)
        return po

    @classmethod
    def cancel_purchase_order(
        cls,
        db: Session,
        po_id: UUID,
        cancel_in: PurchaseOrderCancelRequest,
        current_user: User,
    ) -> PurchaseOrder:
        """Cancel a purchase order."""
        po = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .options(joinedload(PurchaseOrder.items))
        )
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order with ID '{po_id}' not found.",
            )
        if po.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Purchase order '{po.po_number}' has already been cancelled.",
            )
        if po.status == "RECEIVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase order '{po.po_number}' is fully received and cannot be cancelled.",
            )

        po.status = "CANCELLED"
        note_append = f"[CANCELLED on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}: {cancel_in.reason.strip()}]"
        po.notes = f"{po.notes} | {note_append}" if po.notes else note_append
        db.commit()
        db.refresh(po)
        logger.info("Purchase Order cancelled: %s (Reason: %s)", po.po_number, cancel_in.reason)
        return po

    @classmethod
    def _build_po_out(cls, db: Session, po: PurchaseOrder) -> PurchaseOrderOut:
        """Serialize PurchaseOrder ORM object into rich PurchaseOrderOut schema."""
        # Sum confirmed payments on this PO
        total_paid = (
            db.scalar(
                select(func.coalesce(func.sum(SupplierPayment.amount), Decimal("0.00"))).where(
                    and_(
                        SupplierPayment.purchase_order_id == po.id,
                        SupplierPayment.status == "CONFIRMED",
                    )
                )
            )
            or Decimal("0.00")
        )
        outstanding = max(Decimal("0.00"), po.grand_total - total_paid) if po.status != "CANCELLED" else Decimal("0.00")

        total_ordered_qty = sum(item.quantity_ordered for item in po.items) if po.items else 0
        total_received_qty = sum(item.quantity_received for item in po.items) if po.items else 0

        items_out = []
        for item in po.items or []:
            prod = item.product
            var = item.variant
            pending_qty = max(0, item.quantity_ordered - item.quantity_received)
            items_out.append(
                PurchaseOrderItemOut(
                    id=item.id,
                    purchase_order_id=item.purchase_order_id,
                    product_id=item.product_id,
                    product_name=prod.product_name if prod else None,
                    product_code=prod.product_code if prod else None,
                    variant_id=item.variant_id,
                    size=var.size if var else None,
                    color=var.color if var else None,
                    sku=var.sku if var else (prod.sku if prod else None),
                    quantity_ordered=item.quantity_ordered,
                    quantity_received=item.quantity_received,
                    quantity_pending=pending_qty,
                    unit_cost=item.unit_cost,
                    discount_percent=item.discount_percent,
                    tax_percent=item.tax_percent,
                    line_total=item.line_total,
                    created_at=item.created_at,
                )
            )

        return PurchaseOrderOut(
            id=po.id,
            po_number=po.po_number,
            supplier_id=po.supplier_id,
            supplier_name=po.supplier.company_name if po.supplier else None,
            supplier_phone=po.supplier.phone if po.supplier else None,
            po_date=po.po_date,
            order_date=po.po_date,
            expected_delivery_date=po.expected_delivery_date,
            status=po.status,
            subtotal=po.subtotal,
            discount_amount=po.discount_amount,
            discount_total=po.discount_amount,
            tax_amount=po.tax_amount,
            tax_total=po.tax_amount,
            grand_total=po.grand_total,
            total_amount=po.grand_total,
            total_paid=total_paid,
            outstanding_amount=outstanding,
            balance_due=outstanding,
            total_ordered_quantity=total_ordered_qty,
            total_received_quantity=total_received_qty,
            notes=po.notes,
            created_by_user_id=po.created_by_user_id,
            created_by_user_name=po.created_by_user.full_name if po.created_by_user else None,
            items=items_out,
            created_at=po.created_at,
            updated_at=po.updated_at,
        )

    @classmethod
    def get_purchase_order_by_id(cls, db: Session, po_id: UUID) -> PurchaseOrderOut:
        """Get single purchase order by ID."""
        po = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .options(
                joinedload(PurchaseOrder.supplier),
                joinedload(PurchaseOrder.created_by_user),
                joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.product),
                joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.variant),
            )
        )
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order with ID '{po_id}' not found.",
            )
        return cls._build_po_out(db, po)

    @classmethod
    def list_purchase_orders(
        cls,
        db: Session,
        supplier_id: Optional[UUID] = None,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[PurchaseOrderOut], int]:
        """List purchase orders with filtering and search."""
        query = select(PurchaseOrder).join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        filters = []

        if supplier_id:
            filters.append(PurchaseOrder.supplier_id == supplier_id)
        if status_filter:
            filters.append(PurchaseOrder.status == status_filter.strip().upper())
        if date_from:
            filters.append(PurchaseOrder.po_date >= date_from)
        if date_to:
            filters.append(PurchaseOrder.po_date <= date_to)
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(PurchaseOrder.po_number).ilike(term),
                    func.lower(Supplier.company_name).ilike(term),
                )
            )

        if filters:
            query = query.where(and_(*filters))

        count_stmt = select(func.count(PurchaseOrder.id)).join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = db.scalar(count_stmt) or 0

        query = (
            query.options(
                joinedload(PurchaseOrder.supplier),
                joinedload(PurchaseOrder.created_by_user),
                joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.product),
                joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.variant),
            )
            .order_by(PurchaseOrder.po_date.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = db.scalars(query).unique().all()
        results = [cls._build_po_out(db, r) for r in rows]
        return results, total

    # ==========================================================================
    # 3. Goods Receiving / Stock Inward Operations
    # ==========================================================================
    @classmethod
    def receive_goods(
        cls,
        db: Session,
        grn_in: GoodsReceiptCreate,
        current_user: User,
    ) -> GoodsReceiptOut:
        """Atomically record inward goods delivery against an existing Purchase Order.
        Acquires row-level pessimistic locks on inventory, increments stock only for accepted units,
        and logs immutable StockMovement audit records.
        """
        # 1. Fetch Purchase Order with row lock
        po = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == grn_in.purchase_order_id)
            .with_for_update()
        )
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order with ID '{grn_in.purchase_order_id}' not found.",
            )

        # Status validation: Can only receive when ORDERED or PARTIALLY_RECEIVED
        if po.status not in ("ORDERED", "PARTIALLY_RECEIVED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Goods receiving rejected: Purchase order '{po.po_number}' has status '{po.status}'. "
                f"Only orders with status 'ORDERED' or 'PARTIALLY_RECEIVED' can receive goods.",
            )

        # Load purchase order items with product and variant details
        po_items_list = db.scalars(
            select(PurchaseOrderItem)
            .where(PurchaseOrderItem.purchase_order_id == po.id)
            .options(
                joinedload(PurchaseOrderItem.product),
                joinedload(PurchaseOrderItem.variant),
            )
        ).all()
        po_items_map = {item.id: item for item in po_items_list}
        grn_id = uuid.uuid4()
        grn_number = cls.generate_grn_number(db)
        receiving_date = grn_in.receiving_date or datetime.now(timezone.utc)

        receipt_items: List[GoodsReceiptItem] = []
        total_accepted = 0
        total_rejected = 0

        # 2. Process each receipt line
        for item_in in grn_in.items:
            po_item = po_items_map.get(item_in.purchase_order_item_id)
            if not po_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Item '{item_in.purchase_order_item_id}' does not belong to purchase order '{po.po_number}'.",
                )

            # Prevent over-receipt beyond remaining ordered quantity
            remaining_ordered = po_item.quantity_ordered - po_item.quantity_received
            if item_in.quantity_received > remaining_ordered:
                prod_name = po_item.product.product_name if po_item.product else "Item"
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Over-receipt rejected: Cannot receive {item_in.quantity_received} units for '{prod_name}'. "
                    f"Only {remaining_ordered} units are pending on this purchase order.",
                )

            # Update PO item cumulative quantity received
            po_item.quantity_received += item_in.quantity_received

            # Create GRN Line Item
            gr_item = GoodsReceiptItem(
                id=uuid.uuid4(),
                goods_receipt_id=grn_id,
                purchase_order_item_id=po_item.id,
                product_id=po_item.product_id,
                variant_id=po_item.variant_id,
                quantity_received=item_in.quantity_received,
                quantity_accepted=item_in.quantity_accepted,
                quantity_rejected=item_in.quantity_rejected,
                rejection_reason=item_in.rejection_reason.strip() if item_in.rejection_reason else None,
            )
            receipt_items.append(gr_item)
            total_accepted += item_in.quantity_accepted
            total_rejected += item_in.quantity_rejected

            # 3. Inventory and Stock Movement Integration (ONLY FOR ACCEPTED QUANTITY)
            if item_in.quantity_accepted > 0:
                # Row lock on inventory
                inv_stmt = select(Inventory).with_for_update()
                if po_item.variant_id is None:
                    inv_stmt = inv_stmt.where(
                        and_(
                            Inventory.product_id == po_item.product_id,
                            Inventory.variant_id.is_(None),
                        )
                    )
                else:
                    inv_stmt = inv_stmt.where(
                        and_(
                            Inventory.product_id == po_item.product_id,
                            Inventory.variant_id == po_item.variant_id,
                        )
                    )

                inventory = db.scalar(inv_stmt)
                if not inventory:
                    # Create inventory entry if missing
                    inventory = Inventory(
                        id=uuid.uuid4(),
                        product_id=po_item.product_id,
                        variant_id=po_item.variant_id,
                        quantity=item_in.quantity_accepted,
                        low_stock_threshold=5,
                    )
                    db.add(inventory)
                else:
                    inventory.quantity += item_in.quantity_accepted

                # Create immutable StockMovement audit entry
                movement = StockMovement(
                    id=uuid.uuid4(),
                    product_id=po_item.product_id,
                    variant_id=po_item.variant_id,
                    movement_type="PURCHASE",
                    quantity_change=item_in.quantity_accepted,
                    reference_type="GOODS_RECEIPT",
                    reference_id=grn_id,
                    notes=(
                        f"GRN: {grn_number} | PO: {po.po_number} | Supplier: {po.supplier.company_name} | "
                        f"Accepted: {item_in.quantity_accepted}"
                        + (f" | Rejected: {item_in.quantity_rejected}" if item_in.quantity_rejected > 0 else "")
                    ),
                    created_by_user_id=current_user.id,
                )
                db.add(movement)

        # 4. Recalculate Purchase Order Status
        total_ordered_all = sum(item.quantity_ordered for item in po.items)
        total_received_all = sum(item.quantity_received for item in po.items)

        if total_received_all >= total_ordered_all:
            po.status = "RECEIVED"
        elif total_received_all > 0:
            po.status = "PARTIALLY_RECEIVED"

        # 5. Create Goods Receipt record
        grn = GoodsReceipt(
            id=grn_id,
            grn_number=grn_number,
            purchase_order_id=po.id,
            supplier_id=po.supplier_id,
            receiving_date=receiving_date,
            supplier_invoice_ref=(
                (grn_in.supplier_invoice_ref or grn_in.delivery_reference).strip()
                if (grn_in.supplier_invoice_ref or grn_in.delivery_reference)
                else None
            ),
            notes=grn_in.notes.strip() if grn_in.notes else None,
            received_by_user_id=current_user.id,
            total_accepted_quantity=total_accepted,
            total_rejected_quantity=total_rejected,
            items=receipt_items,
        )
        db.add(grn)
        db.commit()
        db.refresh(grn)
        logger.info(
            "Goods Receipt posted: %s against PO %s (Accepted: %s, Rejected: %s, New PO Status: %s)",
            grn.grn_number,
            po.po_number,
            total_accepted,
            total_rejected,
            po.status,
        )
        return cls.get_goods_receipt_by_id(db, grn.id)

    @classmethod
    def get_goods_receipt_by_id(cls, db: Session, grn_id: UUID) -> GoodsReceiptOut:
        """Get single Goods Receipt by ID."""
        grn = db.scalar(
            select(GoodsReceipt)
            .where(GoodsReceipt.id == grn_id)
            .options(
                joinedload(GoodsReceipt.purchase_order),
                joinedload(GoodsReceipt.supplier),
                joinedload(GoodsReceipt.received_by_user),
                joinedload(GoodsReceipt.items).joinedload(GoodsReceiptItem.product),
                joinedload(GoodsReceipt.items).joinedload(GoodsReceiptItem.variant),
            )
        )
        if not grn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Goods receipt with ID '{grn_id}' not found.",
            )

        items_out = []
        for it in grn.items or []:
            prod = it.product
            var = it.variant
            items_out.append(
                GoodsReceiptItemOut(
                    id=it.id,
                    goods_receipt_id=it.goods_receipt_id,
                    purchase_order_item_id=it.purchase_order_item_id,
                    product_id=it.product_id,
                    product_name=prod.product_name if prod else None,
                    product_code=prod.product_code if prod else None,
                    variant_id=it.variant_id,
                    size=var.size if var else None,
                    color=var.color if var else None,
                    sku=var.sku if var else (prod.sku if prod else None),
                    quantity_received=it.quantity_received,
                    quantity_accepted=it.quantity_accepted,
                    quantity_rejected=it.quantity_rejected,
                    rejection_reason=it.rejection_reason,
                    created_at=it.created_at,
                )
            )

        return GoodsReceiptOut(
            id=grn.id,
            grn_number=grn.grn_number,
            purchase_order_id=grn.purchase_order_id,
            po_number=grn.purchase_order.po_number if grn.purchase_order else None,
            supplier_id=grn.supplier_id,
            supplier_name=grn.supplier.company_name if grn.supplier else None,
            receiving_date=grn.receiving_date,
            received_at=grn.receiving_date,
            supplier_invoice_ref=grn.supplier_invoice_ref,
            delivery_reference=grn.supplier_invoice_ref,
            notes=grn.notes,
            received_by_user_id=grn.received_by_user_id,
            received_by_user_name=grn.received_by_user.full_name if grn.received_by_user else None,
            total_accepted_quantity=grn.total_accepted_quantity,
            total_rejected_quantity=grn.total_rejected_quantity,
            total_received_quantity=grn.total_accepted_quantity + grn.total_rejected_quantity,
            items=items_out,
            created_at=grn.created_at,
        )

    @classmethod
    def list_goods_receipts(
        cls,
        db: Session,
        po_id: Optional[UUID] = None,
        supplier_id: Optional[UUID] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[GoodsReceiptOut], int]:
        """List goods receipt notes."""
        query = select(GoodsReceipt).join(Supplier, GoodsReceipt.supplier_id == Supplier.id)
        filters = []

        if po_id:
            filters.append(GoodsReceipt.purchase_order_id == po_id)
        if supplier_id:
            filters.append(GoodsReceipt.supplier_id == supplier_id)
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(GoodsReceipt.grn_number).ilike(term),
                    func.lower(GoodsReceipt.supplier_invoice_ref).ilike(term),
                    func.lower(Supplier.company_name).ilike(term),
                )
            )

        if filters:
            query = query.where(and_(*filters))

        count_stmt = select(func.count(GoodsReceipt.id)).join(Supplier, GoodsReceipt.supplier_id == Supplier.id)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = db.scalar(count_stmt) or 0

        query = (
            query.options(
                joinedload(GoodsReceipt.purchase_order),
                joinedload(GoodsReceipt.supplier),
                joinedload(GoodsReceipt.received_by_user),
                joinedload(GoodsReceipt.items).joinedload(GoodsReceiptItem.product),
                joinedload(GoodsReceipt.items).joinedload(GoodsReceiptItem.variant),
            )
            .order_by(GoodsReceipt.receiving_date.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = db.scalars(query).unique().all()
        results = [cls.get_goods_receipt_by_id(db, r.id) for r in rows]
        return results, total

    # ==========================================================================
    # 4. Supplier Payments
    # ==========================================================================
    @classmethod
    def create_supplier_payment(
        cls,
        db: Session,
        payment_in: SupplierPaymentCreate,
        current_user: User,
    ) -> SupplierPaymentOut:
        """Record a disbursement to a supplier.
        Cash payments may be confirmed immediately; other methods default to PENDING.
        Prevents overpayment beyond outstanding order balance.
        """
        supplier = db.scalar(select(Supplier).where(Supplier.id == payment_in.supplier_id))
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier with ID '{payment_in.supplier_id}' not found.",
            )

        po: Optional[PurchaseOrder] = None
        if payment_in.purchase_order_id:
            po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == payment_in.purchase_order_id))
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Purchase order with ID '{payment_in.purchase_order_id}' not found.",
                )
            if po.supplier_id != supplier.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Purchase order does not belong to the specified supplier.",
                )
            if po.status == "CANCELLED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot record payment against cancelled purchase order '{po.po_number}'.",
                )

            # Prevent overpayment beyond outstanding balance on this PO
            already_confirmed = (
                db.scalar(
                    select(func.coalesce(func.sum(SupplierPayment.amount), Decimal("0.00"))).where(
                        and_(
                            SupplierPayment.purchase_order_id == po.id,
                            SupplierPayment.status == "CONFIRMED",
                        )
                    )
                )
                or Decimal("0.00")
            )
            outstanding_on_po = max(Decimal("0.00"), po.grand_total - already_confirmed)
            if payment_in.amount > outstanding_on_po:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Overpayment rejected: Requested payment amount Rs. {payment_in.amount} "
                    f"exceeds purchase order outstanding balance of Rs. {outstanding_on_po}.",
                )

        payment_number = cls.generate_payment_number(db)
        method = payment_in.payment_method.strip().upper()

        # CASH is immediately CONFIRMED if handed over; UPI/BANK_TRANSFER/CHEQUE defaults to PENDING
        if method == "CASH":
            initial_status = "CONFIRMED"
            confirmed_at = datetime.now(timezone.utc)
            confirmed_by = current_user.id
        else:
            initial_status = "PENDING"
            confirmed_at = None
            confirmed_by = None

        payment = SupplierPayment(
            id=uuid.uuid4(),
            payment_number=payment_number,
            supplier_id=payment_in.supplier_id,
            purchase_order_id=payment_in.purchase_order_id,
            payment_date=payment_in.payment_date or datetime.now(timezone.utc),
            payment_method=method,
            amount=payment_in.amount,
            status=initial_status,
            transaction_reference=payment_in.transaction_reference.strip() if payment_in.transaction_reference else None,
            notes=payment_in.notes.strip() if payment_in.notes else None,
            confirmed_at=confirmed_at,
            confirmed_by_user_id=confirmed_by,
            created_by_user_id=current_user.id,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        logger.info(
            "Supplier payment recorded: %s (Amount: Rs. %s, Method: %s, Status: %s)",
            payment.payment_number,
            payment.amount,
            payment.payment_method,
            payment.status,
        )
        return cls._build_payment_out(db, payment)

    @classmethod
    def confirm_supplier_payment(
        cls,
        db: Session,
        payment_id: UUID,
        confirm_in: SupplierPaymentConfirmRequest,
        current_owner: User,
    ) -> SupplierPaymentOut:
        """Owner confirms a PENDING supplier payment after clearance."""
        payment = db.scalar(
            select(SupplierPayment)
            .where(SupplierPayment.id == payment_id)
            .with_for_update()
        )
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier payment with ID '{payment_id}' not found.",
            )
        if payment.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm payment '{payment.payment_number}': Status is '{payment.status}'. Only PENDING payments can be confirmed.",
            )

        # Check overpayment at confirmation time if linked to PO
        if payment.purchase_order_id and payment.purchase_order:
            po = payment.purchase_order
            already_confirmed = (
                db.scalar(
                    select(func.coalesce(func.sum(SupplierPayment.amount), Decimal("0.00"))).where(
                        and_(
                            SupplierPayment.purchase_order_id == po.id,
                            SupplierPayment.status == "CONFIRMED",
                            SupplierPayment.id != payment.id,
                        )
                    )
                )
                or Decimal("0.00")
            )
            outstanding_on_po = max(Decimal("0.00"), po.grand_total - already_confirmed)
            if payment.amount > outstanding_on_po:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Confirmation rejected: Payment amount Rs. {payment.amount} exceeds remaining PO balance Rs. {outstanding_on_po}.",
                )

        payment.status = "CONFIRMED"
        payment.confirmed_at = datetime.now(timezone.utc)
        payment.confirmed_by_user_id = current_owner.id
        if confirm_in.transaction_reference:
            payment.transaction_reference = confirm_in.transaction_reference.strip()
        if confirm_in.notes:
            payment.notes = f"{payment.notes} | {confirm_in.notes.strip()}" if payment.notes else confirm_in.notes.strip()

        db.commit()
        db.refresh(payment)
        logger.info("Supplier payment confirmed: %s by %s", payment.payment_number, current_owner.email)
        return cls._build_payment_out(db, payment)

    @classmethod
    def reject_supplier_payment(
        cls,
        db: Session,
        payment_id: UUID,
        reject_in: SupplierPaymentRejectRequest,
        current_owner: User,
    ) -> SupplierPaymentOut:
        """Owner rejects a PENDING supplier payment."""
        payment = db.scalar(select(SupplierPayment).where(SupplierPayment.id == payment_id).with_for_update())
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier payment with ID '{payment_id}' not found.",
            )
        if payment.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject payment '{payment.payment_number}': Status is '{payment.status}'. Only PENDING payments can be rejected.",
            )

        payment.status = "REJECTED"
        payment.rejection_reason = reject_in.rejection_reason.strip()
        db.commit()
        db.refresh(payment)
        logger.info("Supplier payment rejected: %s (Reason: %s)", payment.payment_number, reject_in.rejection_reason)
        return cls._build_payment_out(db, payment)

    @classmethod
    def _build_payment_out(cls, db: Session, payment: SupplierPayment) -> SupplierPaymentOut:
        """Serialize SupplierPayment model to SupplierPaymentOut schema."""
        return SupplierPaymentOut(
            id=payment.id,
            payment_number=payment.payment_number,
            supplier_id=payment.supplier_id,
            supplier_name=payment.supplier.company_name if payment.supplier else None,
            purchase_order_id=payment.purchase_order_id,
            po_number=payment.purchase_order.po_number if payment.purchase_order else None,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            amount=payment.amount,
            status=payment.status,
            transaction_reference=payment.transaction_reference,
            notes=payment.notes,
            rejection_reason=payment.rejection_reason,
            confirmed_at=payment.confirmed_at,
            confirmed_by_user_id=payment.confirmed_by_user_id,
            confirmed_by_user_name=payment.confirmed_by_user.full_name if payment.confirmed_by_user else None,
            created_by_user_id=payment.created_by_user_id,
            created_by_user_name=payment.created_by_user.full_name if payment.created_by_user else None,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )

    @classmethod
    def list_supplier_payments(
        cls,
        db: Session,
        supplier_id: Optional[UUID] = None,
        po_id: Optional[UUID] = None,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[SupplierPaymentOut], int]:
        """List supplier payment transactions."""
        query = select(SupplierPayment).join(Supplier, SupplierPayment.supplier_id == Supplier.id)
        filters = []
        if supplier_id:
            filters.append(SupplierPayment.supplier_id == supplier_id)
        if po_id:
            filters.append(SupplierPayment.purchase_order_id == po_id)
        if status_filter:
            filters.append(SupplierPayment.status == status_filter.strip().upper())

        if filters:
            query = query.where(and_(*filters))

        count_stmt = select(func.count(SupplierPayment.id)).join(Supplier, SupplierPayment.supplier_id == Supplier.id)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = db.scalar(count_stmt) or 0

        query = (
            query.options(
                joinedload(SupplierPayment.supplier),
                joinedload(SupplierPayment.purchase_order),
                joinedload(SupplierPayment.created_by_user),
                joinedload(SupplierPayment.confirmed_by_user),
            )
            .order_by(SupplierPayment.payment_date.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = db.scalars(query).unique().all()
        results = [cls._build_payment_out(db, p) for p in rows]
        return results, total

    # ==========================================================================
    # 5. Purchase Analytics & Summary
    # ==========================================================================
    @classmethod
    def get_purchase_summary(
        cls,
        db: Session,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> PurchaseSummaryOut:
        """Compute real-time purchase metrics and supplier liability overview."""
        filters = [PurchaseOrder.status != "CANCELLED"]
        if date_from:
            filters.append(PurchaseOrder.po_date >= date_from)
        if date_to:
            filters.append(PurchaseOrder.po_date <= date_to)

        # 1. Total POs and Total Ordered Value
        po_stat_query = select(
            func.count(PurchaseOrder.id),
            func.coalesce(func.sum(PurchaseOrder.grand_total), Decimal("0.00")),
        ).where(and_(*filters))
        po_count, total_ordered_val = db.execute(po_stat_query).one()

        # 2. Total Goods Received Value (accepted items * unit_cost)
        grn_filter = []
        if date_from:
            grn_filter.append(GoodsReceipt.receiving_date >= date_from)
        if date_to:
            grn_filter.append(GoodsReceipt.receiving_date <= date_to)

        grn_query = (
            select(
                func.coalesce(
                    func.sum(GoodsReceiptItem.quantity_accepted * PurchaseOrderItem.unit_cost),
                    Decimal("0.00"),
                )
            )
            .join(GoodsReceipt, GoodsReceiptItem.goods_receipt_id == GoodsReceipt.id)
            .join(PurchaseOrderItem, GoodsReceiptItem.purchase_order_item_id == PurchaseOrderItem.id)
        )
        if grn_filter:
            grn_query = grn_query.where(and_(*grn_filter))
        total_grn_val = db.scalar(grn_query) or Decimal("0.00")

        # 3. Confirmed & Pending Payments
        pmt_filter = []
        if date_from:
            pmt_filter.append(SupplierPayment.payment_date >= date_from)
        if date_to:
            pmt_filter.append(SupplierPayment.payment_date <= date_to)

        confirmed_query = select(func.coalesce(func.sum(SupplierPayment.amount), Decimal("0.00"))).where(
            and_(SupplierPayment.status == "CONFIRMED", *pmt_filter)
        )
        total_confirmed_pmts = db.scalar(confirmed_query) or Decimal("0.00")

        pending_query = select(func.coalesce(func.sum(SupplierPayment.amount), Decimal("0.00"))).where(
            and_(SupplierPayment.status == "PENDING", *pmt_filter)
        )
        total_pending_pmts = db.scalar(pending_query) or Decimal("0.00")

        # 4. Total Supplier Outstanding (All active PO liability - confirmed payments)
        all_po_val = (
            db.scalar(
                select(func.coalesce(func.sum(PurchaseOrder.grand_total), Decimal("0.00"))).where(
                    PurchaseOrder.status != "CANCELLED"
                )
            )
            or Decimal("0.00")
        )
        all_confirmed_pmts = (
            db.scalar(
                select(func.coalesce(func.sum(SupplierPayment.amount), Decimal("0.00"))).where(
                    SupplierPayment.status == "CONFIRMED"
                )
            )
            or Decimal("0.00")
        )
        total_supplier_outstanding = max(Decimal("0.00"), all_po_val - all_confirmed_pmts)

        # 5. Active Suppliers
        active_suppliers = db.scalar(select(func.count(Supplier.id)).where(Supplier.is_active.is_(True))) or 0

        # 6. Status Breakdown
        status_stmt = select(PurchaseOrder.status, func.count(PurchaseOrder.id)).group_by(PurchaseOrder.status)
        status_rows = db.execute(status_stmt).all()
        status_counts = {st: 0 for st in ["DRAFT", "ORDERED", "PARTIALLY_RECEIVED", "RECEIVED", "CANCELLED"]}
        for st, cnt in status_rows:
            status_counts[st] = cnt

        return PurchaseSummaryOut(
            total_purchase_orders=int(po_count),
            total_ordered_value=total_ordered_val,
            total_goods_received_value=total_grn_val,
            total_confirmed_payments=total_confirmed_pmts,
            total_pending_payments=total_pending_pmts,
            total_supplier_outstanding=total_supplier_outstanding,
            active_suppliers_count=int(active_suppliers),
            status_counts=status_counts,
        )

    # ==========================================================================
    # 7. Purchase Order Deletion (Owner Only)
    # ==========================================================================
    @classmethod
    def delete_purchase_order(
        cls,
        db: Session,
        po_id: UUID,
        current_owner: User,
    ) -> dict:
        """Safely delete an eligible purchase order (Owner Only).

        Blocks deletion if:
        - Goods Receipts have already been recorded (inventory was received)
        - Supplier Payments have already been linked
        Cascade-deletes line items and records an audit log.
        """
        po = db.scalar(
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .options(
                joinedload(PurchaseOrder.goods_receipts),
                joinedload(PurchaseOrder.payments),
                joinedload(PurchaseOrder.items),
            )
            .with_for_update()
        )
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order with ID '{po_id}' was not found.",
            )

        if po.goods_receipts and len(po.goods_receipts) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot delete Purchase Order '{po.po_number}': it has {len(po.goods_receipts)} "
                    "completed Goods Receipt(s) that already added stock to inventory. "
                    "Reversal must be handled via Goods Receipt adjustments."
                ),
            )

        if po.payments and len(po.payments) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot delete Purchase Order '{po.po_number}': it has {len(po.payments)} "
                    "linked Supplier Payment transaction(s). Settle or void payments first."
                ),
            )

        po_number = po.po_number
        now_utc = datetime.now(timezone.utc)
        audit = AuditLog(
            id=uuid.uuid4(),
            user_id=current_owner.id,
            action="PURCHASE_ORDER_DELETED",
            entity_type="PURCHASE_ORDER",
            entity_id=po.id,
            old_values={
                "po_number": po_number,
                "status": po.status,
                "supplier_id": str(po.supplier_id),
                "grand_total": str(po.grand_total),
                "items_count": len(po.items),
            },
            new_values={
                "deleted": True,
                "actioned_by": str(current_owner.id),
            },
            created_at=now_utc,
        )
        db.add(audit)
        db.delete(po)
        db.commit()

        return {
            "message": f"Purchase Order '{po_number}' was successfully deleted.",
            "deleted": True,
            "po_id": str(po_id),
        }
