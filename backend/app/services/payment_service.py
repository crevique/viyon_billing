"""Payment processing, cash recording, UPI confirmation, and split payment service."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.bill import Bill
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import (
    PaymentConfirmRequest,
    PaymentCreate,
    PaymentListResponse,
    PaymentOut,
    PaymentRejectRequest,
)

logger = logging.getLogger("viyon_billing.payments")


class PaymentService:
    """Service layer managing payments, split payments, and manual UPI verifications."""

    @classmethod
    def record_payment(
        cls,
        db: Session,
        bill_id: UUID,
        payment_in: PaymentCreate,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> PaymentOut:
        """Atomically record a payment (CASH or UPI) against a bill with row-level locks."""
        # 1. Pessimistic lock on Bill row
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
                detail="Cannot record payment for a CANCELLED bill.",
            )

        if bill.bill_status == "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot record payment for a DRAFT bill.",
            )

        # 2. Recompute authoritative confirmed payments sum from DB records
        confirmed_sum = db.scalar(
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .where(
                Payment.bill_id == bill_id,
                Payment.payment_status == "CONFIRMED",
            )
        ) or Decimal("0.00")

        current_balance = (bill.total_amount - confirmed_sum).quantize(Decimal("0.01"))
        if current_balance <= Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Bill '{bill.bill_number}' is already fully paid.",
            )

        # 3. Validate payment amount
        payment_amount = payment_in.amount.quantize(Decimal("0.01"))
        if payment_amount <= Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount must be greater than zero.",
            )

        if payment_amount > current_balance:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payment amount (Rs. {payment_amount}) exceeds outstanding bill balance "
                    f"(Rs. {current_balance})."
                ),
            )

        # Check total recorded payments (CONFIRMED + PENDING) to prevent over-recording
        total_recorded = db.scalar(
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .where(
                Payment.bill_id == bill_id,
                Payment.payment_status.in_(["CONFIRMED", "PENDING"]),
            )
        ) or Decimal("0.00")

        unrecorded_balance = (bill.total_amount - total_recorded).quantize(Decimal("0.01"))
        if payment_amount > unrecorded_balance:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payment amount (Rs. {payment_amount}) exceeds remaining payable balance "
                    f"(Rs. {unrecorded_balance})."
                ),
            )

        # 4. Validate duplicate UTR / transaction reference
        cleaned_ref = payment_in.transaction_reference
        if cleaned_ref:
            duplicate = db.scalar(
                select(Payment).where(
                    Payment.transaction_reference == cleaned_ref,
                    Payment.payment_status.in_(["CONFIRMED", "PENDING"]),
                )
            )
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Transaction reference '{cleaned_ref}' is already associated with "
                        f"existing payment ID '{duplicate.id}'."
                    ),
                )

        # 5. Determine confirmation status
        now_utc = datetime.now(timezone.utc)
        # All counter payments (CASH and UPI) are immediately confirmed as PAID
        is_confirmed = True
        payment_status_val = "CONFIRMED" if is_confirmed else "PENDING"
        confirmed_by = current_user.id if is_confirmed else None
        confirmed_at_val = now_utc if is_confirmed else None

        # 6. Insert Payment Record
        payment = Payment(
            id=uuid4(),
            bill_id=bill.id,
            payment_method=payment_in.payment_method,
            amount=payment_amount,
            payment_status=payment_status_val,
            transaction_reference=cleaned_ref,
            received_by_user_id=current_user.id,
            received_at=now_utc,
            confirmed_by_user_id=confirmed_by,
            confirmed_at=confirmed_at_val,
            notes=payment_in.notes.strip() if payment_in.notes else None,
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(payment)
        db.flush()

        # 7. Update Bill totals if confirmed
        if is_confirmed:
            new_amount_paid = (confirmed_sum + payment_amount).quantize(Decimal("0.01"))
            new_balance = (bill.total_amount - new_amount_paid).quantize(Decimal("0.01"))

            bill.amount_paid = new_amount_paid
            bill.balance_amount = new_balance
            bill.payment_status = "PAID" if new_balance == Decimal("0.00") else "PARTIALLY_PAID"
            bill.updated_at = now_utc

        # 8. Record in Audit Log
        audit = AuditLog(
            id=uuid4(),
            user_id=current_user.id,
            action=f"PAYMENT_RECORDED_{payment_status_val}",
            entity_type="PAYMENT",
            entity_id=payment.id,
            new_values={
                "bill_id": str(bill.id),
                "bill_number": bill.bill_number,
                "amount": str(payment_amount),
                "payment_method": payment.payment_method,
                "payment_status": payment.payment_status,
                "transaction_reference": payment.transaction_reference,
                "is_confirmed": is_confirmed,
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)

        db.commit()
        db.refresh(payment)
        db.refresh(bill)

        logger.info(
            f"Payment recorded: ID={payment.id} Method={payment.payment_method} "
            f"Amount={payment.amount} Status={payment.payment_status} Bill={bill.bill_number}"
        )

        return cls._build_payment_out(payment, bill)

    @classmethod
    def confirm_payment(
        cls,
        db: Session,
        payment_id: UUID,
        confirm_in: PaymentConfirmRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> PaymentOut:
        """Confirm a pending UPI payment after staff verifies receipt in bank account."""
        # 1. Fetch payment to know the bill_id
        payment_preview = db.scalar(select(Payment).where(Payment.id == payment_id))
        if not payment_preview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID '{payment_id}' was not found.",
            )

        # 2. Acquire locks in strict hierarchical order: Bill FIRST, then Payment
        bill = db.scalar(
            select(Bill)
            .where(Bill.id == payment_preview.bill_id)
            .with_for_update()
        )
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bill associated with payment '{payment_id}' was not found.",
            )

        if bill.bill_status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot confirm payment for a CANCELLED bill.",
            )

        payment = db.scalar(
            select(Payment)
            .where(Payment.id == payment_id)
            .with_for_update()
        )
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID '{payment_id}' was not found.",
            )

        # 3. Validate payment state
        if payment.payment_status == "CONFIRMED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment has already been confirmed.",
            )

        if payment.payment_status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot confirm payment with status '{payment.payment_status}'. Only PENDING payments can be confirmed.",
            )

        # 4. Check outstanding balance
        confirmed_sum = db.scalar(
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .where(
                Payment.bill_id == bill.id,
                Payment.payment_status == "CONFIRMED",
            )
        ) or Decimal("0.00")

        current_balance = (bill.total_amount - confirmed_sum).quantize(Decimal("0.01"))
        if payment.amount > current_balance:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payment amount (Rs. {payment.amount}) exceeds outstanding bill balance "
                    f"(Rs. {current_balance})."
                ),
            )

        # 5. Check duplicate UTR among other confirmed payments
        if payment.transaction_reference:
            dup_utr = db.scalar(
                select(Payment).where(
                    Payment.transaction_reference == payment.transaction_reference,
                    Payment.payment_status == "CONFIRMED",
                    Payment.id != payment.id,
                )
            )
            if dup_utr:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Transaction reference '{payment.transaction_reference}' is already confirmed on payment ID '{dup_utr.id}'.",
                )

        # 6. Apply Confirmation
        now_utc = datetime.now(timezone.utc)
        payment.payment_status = "CONFIRMED"
        payment.confirmed_by_user_id = current_user.id
        payment.confirmed_at = now_utc
        payment.updated_at = now_utc
        if confirm_in.notes:
            existing_note = payment.notes or ""
            payment.notes = f"{existing_note} | Confirmed: {confirm_in.notes.strip()}".strip(" |")

        # 7. Update Bill totals
        new_amount_paid = (confirmed_sum + payment.amount).quantize(Decimal("0.01"))
        new_balance = (bill.total_amount - new_amount_paid).quantize(Decimal("0.01"))

        bill.amount_paid = new_amount_paid
        bill.balance_amount = new_balance
        bill.payment_status = "PAID" if new_balance == Decimal("0.00") else "PARTIALLY_PAID"
        bill.updated_at = now_utc

        # 8. Record in Audit Log
        audit = AuditLog(
            id=uuid4(),
            user_id=current_user.id,
            action="PAYMENT_CONFIRMED",
            entity_type="PAYMENT",
            entity_id=payment.id,
            old_values={"payment_status": "PENDING"},
            new_values={
                "payment_status": "CONFIRMED",
                "confirmed_by_user_id": str(current_user.id),
                "amount": str(payment.amount),
                "bill_id": str(bill.id),
                "bill_number": bill.bill_number,
                "bill_balance_amount": str(new_balance),
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)

        db.commit()
        db.refresh(payment)
        db.refresh(bill)

        logger.info(
            f"Payment confirmed: ID={payment.id} Amount={payment.amount} Bill={bill.bill_number} "
            f"NewBalance={bill.balance_amount}"
        )

        return cls._build_payment_out(payment, bill)

    @classmethod
    def reject_payment(
        cls,
        db: Session,
        payment_id: UUID,
        reject_in: PaymentRejectRequest,
        current_user: User,
        ip_address: Optional[str] = None,
    ) -> PaymentOut:
        """Reject an unverified or disputed pending UPI payment."""
        payment_preview = db.scalar(select(Payment).where(Payment.id == payment_id))
        if not payment_preview:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID '{payment_id}' was not found.",
            )

        # Lock in consistent order: Bill, then Payment
        bill = db.scalar(
            select(Bill)
            .where(Bill.id == payment_preview.bill_id)
            .with_for_update()
        )
        payment = db.scalar(
            select(Payment)
            .where(Payment.id == payment_id)
            .with_for_update()
        )
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID '{payment_id}' was not found.",
            )

        if payment.payment_status == "CONFIRMED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot reject an already CONFIRMED payment. Payment reversals require refund procedures.",
            )

        if payment.payment_status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reject payment with status '{payment.payment_status}'. Only PENDING payments can be rejected.",
            )

        now_utc = datetime.now(timezone.utc)
        payment.payment_status = "REJECTED"
        payment.confirmed_by_user_id = current_user.id
        payment.rejection_reason = reject_in.rejection_reason.strip()
        payment.updated_at = now_utc
        if reject_in.notes:
            existing_note = payment.notes or ""
            payment.notes = f"{existing_note} | Reject Note: {reject_in.notes.strip()}".strip(" |")

        # Note: Bill totals are untouched because rejected payment never added to amount_paid

        # Audit log
        audit = AuditLog(
            id=uuid4(),
            user_id=current_user.id,
            action="PAYMENT_REJECTED",
            entity_type="PAYMENT",
            entity_id=payment.id,
            old_values={"payment_status": "PENDING"},
            new_values={
                "payment_status": "REJECTED",
                "rejection_reason": payment.rejection_reason,
                "rejected_by_user_id": str(current_user.id),
                "bill_id": str(payment.bill_id),
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)

        db.commit()
        db.refresh(payment)

        logger.info(
            f"Payment rejected: ID={payment.id} Bill={payment.bill_id} Reason='{payment.rejection_reason}'"
        )

        return cls._build_payment_out(payment, bill)

    @classmethod
    def get_payment_by_id(cls, db: Session, payment_id: UUID) -> PaymentOut:
        """Retrieve a specific payment by its UUID."""
        stmt = (
            select(Payment, Bill)
            .join(Bill, Payment.bill_id == Bill.id)
            .where(Payment.id == payment_id)
        )
        result = db.execute(stmt).first()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID '{payment_id}' was not found.",
            )
        payment, bill = result[0], result[1]
        return cls._build_payment_out(payment, bill)

    @classmethod
    def get_bill_payments(cls, db: Session, bill_id: UUID) -> List[PaymentOut]:
        """Retrieve all payment records associated with a specific bill."""
        bill = db.scalar(select(Bill).where(Bill.id == bill_id))
        if not bill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bill with ID '{bill_id}' was not found.",
            )

        stmt = (
            select(Payment)
            .where(Payment.bill_id == bill_id)
            .order_by(Payment.created_at.asc())
        )
        payments = list(db.scalars(stmt).all())
        return [cls._build_payment_out(p, bill) for p in payments]

    @classmethod
    def list_payments(
        cls,
        db: Session,
        payment_method: Optional[str] = None,
        payment_status: Optional[str] = None,
        bill_number: Optional[str] = None,
        transaction_reference: Optional[str] = None,
        user_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PaymentListResponse:
        """Paginated search across store payment records."""
        base_stmt = select(Payment).join(Bill, Payment.bill_id == Bill.id)

        if payment_method:
            clean_m = payment_method.strip().upper()
            base_stmt = base_stmt.where(Payment.payment_method == clean_m)

        if payment_status:
            clean_s = payment_status.strip().upper()
            base_stmt = base_stmt.where(Payment.payment_status == clean_s)

        if bill_number:
            base_stmt = base_stmt.where(Bill.bill_number.ilike(f"%{bill_number.strip()}%"))

        if transaction_reference:
            base_stmt = base_stmt.where(
                Payment.transaction_reference.ilike(f"%{transaction_reference.strip()}%")
            )

        if user_id:
            base_stmt = base_stmt.where(
                (Payment.received_by_user_id == user_id)
                | (Payment.confirmed_by_user_id == user_id)
            )

        if start_date:
            base_stmt = base_stmt.where(Payment.created_at >= start_date)

        if end_date:
            base_stmt = base_stmt.where(Payment.created_at <= end_date)

        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = db.scalar(total_stmt) or 0

        paginated_stmt = (
            select(Payment, Bill)
            .join(Bill, Payment.bill_id == Bill.id)
            .where(
                Payment.id.in_(
                    base_stmt.with_only_columns(Payment.id)
                    .order_by(Payment.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .order_by(Payment.created_at.desc())
        )

        rows = db.execute(paginated_stmt).all()
        items = [cls._build_payment_out(p, b) for p, b in rows]

        return PaymentListResponse(
            total=total,
            items=items,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _build_payment_out(payment: Payment, bill: Optional[Bill] = None) -> PaymentOut:
        """Build PaymentOut schema with associated bill summary."""
        return PaymentOut(
            id=payment.id,
            bill_id=payment.bill_id,
            payment_method=payment.payment_method,
            amount=payment.amount,
            payment_status=payment.payment_status,
            transaction_reference=payment.transaction_reference,
            received_by_user_id=payment.received_by_user_id,
            received_at=payment.received_at,
            confirmed_by_user_id=payment.confirmed_by_user_id,
            confirmed_at=payment.confirmed_at,
            rejection_reason=payment.rejection_reason,
            notes=payment.notes,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
            bill_number=bill.bill_number if bill else None,
            bill_total_amount=bill.total_amount if bill else None,
            bill_amount_paid=bill.amount_paid if bill else None,
            bill_balance_amount=bill.balance_amount if bill else None,
            bill_payment_status=bill.payment_status if bill else None,
        )
