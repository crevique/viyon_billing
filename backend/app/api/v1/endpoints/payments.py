"""API endpoints for payment management, UPI verification, rejection, and payment queries."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_staff_or_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.payment import (
    PaymentConfirmRequest,
    PaymentListResponse,
    PaymentOut,
    PaymentRejectRequest,
)
from app.services.payment_service import PaymentService

router = APIRouter()


@router.get(
    "",
    response_model=PaymentListResponse,
    summary="List Store Payments (Staff & Owner)",
    description=(
        "Search and filter store payment transactions by payment method, status, "
        "bill number, UTR transaction reference, user, and date range."
    ),
)
def list_payments(
    payment_method: Optional[str] = Query(default=None, description="Filter by method: CASH or UPI"),
    payment_status: Optional[str] = Query(
        default=None,
        description="Filter by status: PENDING, CONFIRMED, REJECTED, FAILED, REFUNDED",
    ),
    bill_number: Optional[str] = Query(default=None, description="Search by bill number"),
    transaction_reference: Optional[str] = Query(
        default=None, description="Search by UPI reference / UTR"
    ),
    user_id: Optional[UUID] = Query(
        default=None, description="Filter by staff cashier or verifier user UUID"
    ),
    start_date: Optional[datetime] = Query(default=None, description="Start date/time"),
    end_date: Optional[datetime] = Query(default=None, description="End date/time"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> PaymentListResponse:
    """Retrieve paginated payment records."""
    return PaymentService.list_payments(
        db=db,
        payment_method=payment_method,
        payment_status=payment_status,
        bill_number=bill_number,
        transaction_reference=transaction_reference,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentOut,
    summary="Get Payment by ID (Staff & Owner)",
    description="Retrieve full details for an individual payment transaction.",
)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> PaymentOut:
    """Retrieve a single payment record by UUID."""
    return PaymentService.get_payment_by_id(db, payment_id)


@router.patch(
    "/{payment_id}/confirm",
    response_model=PaymentOut,
    summary="Confirm Pending UPI Payment (Staff & Owner)",
    description=(
        "Manually confirm receipt of a pending UPI payment after staff verification on store bank account/app. "
        "Atomically increments the bill's amount_paid and decrements outstanding balance."
    ),
)
def confirm_payment(
    payment_id: UUID,
    confirm_in: PaymentConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> PaymentOut:
    """Confirm a pending payment."""
    client_ip = request.client.host if request.client else None
    return PaymentService.confirm_payment(
        db=db,
        payment_id=payment_id,
        confirm_in=confirm_in,
        current_user=current_user,
        ip_address=client_ip,
    )


@router.patch(
    "/{payment_id}/reject",
    response_model=PaymentOut,
    summary="Reject Pending UPI Payment (Staff & Owner)",
    description=(
        "Reject an unverified or disputed pending UPI payment with a mandatory reason. "
        "Does not modify bill paid amounts."
    ),
)
def reject_payment(
    payment_id: UUID,
    reject_in: PaymentRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> PaymentOut:
    """Reject a pending payment."""
    client_ip = request.client.host if request.client else None
    return PaymentService.reject_payment(
        db=db,
        payment_id=payment_id,
        reject_in=reject_in,
        current_user=current_user,
        ip_address=client_ip,
    )
