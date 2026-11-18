"""API endpoints for in-store sales checkout, bill creation, and invoice queries."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_staff_or_owner, require_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.bill import BillCreate, BillCancelRequest, BillOut, BillItemOut, BillListResponse
from app.schemas.payment import PaymentCreate, PaymentOut
from app.schemas.receipt import (
    ReceiptOut,
    ReceiptPreviewOut,
    ReceiptPrintAuditRequest,
    ReceiptPrintAuditResponse,
)
from app.services.billing_service import BillingService
from app.services.payment_service import PaymentService
from app.services.receipt_service import ReceiptService

router = APIRouter()


@router.post(
    "",
    response_model=BillOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Sales Bill & Checkout (Staff & Owner)",
    description=(
        "Atomically validate cart items, lock inventory with row-locking, deduct stock, "
        "compute financial gross, discount, and tax totals, and record immutable sale ledger entries."
    ),
)
def create_bill(
    bill_in: BillCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> BillOut:
    """Create a new bill and process checkout."""
    client_ip = request.client.host if request.client else None
    try:
        bill = BillingService.create_bill(db, bill_in, current_user, ip_address=client_ip)
        return BillingService._build_bill_out(bill)
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg or "does not exist" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        if "Insufficient stock" in err_msg or "archived" in err_msg or "inactive" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=err_msg,
            )
        if "already associated" in err_msg or "exceeds" in err_msg or "already fully paid" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=err_msg,
            )
        if "discount" in err_msg.lower() or "cart" in err_msg.lower() or "variant_id" in err_msg or "payment" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )


@router.get(
    "",
    response_model=BillListResponse,
    summary="List Sales Bills (Staff & Owner)",
    description="Retrieve paginated bill invoices with search by bill number, customer, status, payment method, and date filters.",
)
def list_bills(
    search: Optional[str] = Query(default=None, description="Search by bill number"),
    bill_number: Optional[str] = Query(default=None, description="Filter specifically by bill number"),
    customer_id: Optional[UUID] = Query(default=None, description="Filter by customer UUID"),
    customer_name: Optional[str] = Query(default=None, description="Filter by customer name"),
    customer_phone: Optional[str] = Query(default=None, description="Filter by customer phone number"),
    staff_user_id: Optional[UUID] = Query(default=None, description="Filter by staff cashier UUID"),
    bill_status: Optional[str] = Query(default=None, description="Filter by bill status: DRAFT, COMPLETED, CANCELLED"),
    payment_status: Optional[str] = Query(
        default=None,
        description="Filter by payment status: PENDING, PARTIALLY_PAID, PAID, REFUNDED",
    ),
    payment_method: Optional[str] = Query(default=None, description="Filter by payment method: CASH or UPI"),
    is_cancelled: Optional[bool] = Query(default=None, description="Filter cancelled (true) or active (false) bills"),
    start_date: Optional[datetime] = Query(default=None, description="Start date/time"),
    end_date: Optional[datetime] = Query(default=None, description="End date/time"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc|ASC|DESC)$", description="Sort order: 'desc' or 'asc'"),
    page: Optional[int] = Query(default=None, ge=1, description="Page number (1-based)"),
    page_size: Optional[int] = Query(default=None, ge=1, le=100, description="Items per page"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page (offset-based)"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> BillListResponse:
    """List bills with filters and pagination."""
    items, total, eff_limit, eff_offset, eff_page, total_pages = BillingService.list_bills(
        db=db,
        search=search,
        bill_number=bill_number,
        customer_id=customer_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        staff_user_id=staff_user_id,
        bill_status=bill_status,
        payment_status=payment_status,
        payment_method=payment_method,
        is_cancelled=is_cancelled,
        start_date=start_date,
        end_date=end_date,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
        limit=limit,
        offset=offset,
    )
    return BillListResponse(
        items=items,
        total=total,
        limit=eff_limit,
        offset=eff_offset,
        page=eff_page,
        page_size=eff_limit,
        total_records=total,
        total_pages=total_pages,
    )


@router.get(
    "/receipt/by-number/{bill_number}",
    response_model=ReceiptOut,
    summary="Get Receipt by Bill Number (Staff & Owner)",
    description="Retrieve structured 58mm thermal receipt data using human-readable bill number.",
)
def get_receipt_by_number(
    bill_number: str,
    is_reprint: bool = Query(default=False, description="Flag indicating duplicate/reprint copy"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> ReceiptOut:
    """Retrieve receipt data by bill number."""
    try:
        return ReceiptService.get_receipt_data_by_number(
            db, bill_number=bill_number, is_reprint=is_reprint
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{bill_id}",
    response_model=BillOut,
    summary="Get Bill by ID (Staff & Owner)",
    description="Retrieve complete invoice details including customer, cashier, totals, and line items.",
)
def get_bill(
    bill_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> BillOut:
    """Fetch bill by UUID."""
    bill = BillingService.get_bill_by_id(db, bill_id)
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bill with ID '{bill_id}' was not found.",
        )
    return BillingService._build_bill_out(bill)


@router.get(
    "/{bill_id}/items",
    response_model=List[BillItemOut],
    summary="Get Bill Line Items (Staff & Owner)",
    description="Retrieve frozen snapshot line items for a specific bill.",
)
def get_bill_items(
    bill_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> List[BillItemOut]:
    """Fetch line items for a bill."""
    bill = BillingService.get_bill_by_id(db, bill_id)
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bill with ID '{bill_id}' was not found.",
        )
    return BillingService.get_bill_items(db, bill_id)


@router.get(
    "/{bill_id}/receipt",
    response_model=ReceiptOut,
    summary="Get Structured Receipt Data (Staff & Owner)",
    description=(
        "Retrieve complete 58mm thermal receipt data including historical snapshots, "
        "payment breakdown, cancellation information, and 32-column formatted text."
    ),
)
def get_bill_receipt(
    bill_id: UUID,
    is_reprint: bool = Query(default=False, description="Flag indicating duplicate/reprint copy"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> ReceiptOut:
    """Retrieve structured 58mm thermal receipt data for a bill."""
    try:
        return ReceiptService.get_receipt_data(db, bill_id=bill_id, is_reprint=is_reprint)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{bill_id}/receipt/preview",
    response_model=ReceiptPreviewOut,
    summary="Get Receipt Preview (Staff & Owner)",
    description=(
        "Retrieve 58mm thermal receipt preview including structured data, "
        "32-column monospace formatted text, and standalone print-ready HTML."
    ),
)
def get_bill_receipt_preview(
    bill_id: UUID,
    is_reprint: bool = Query(default=False, description="Flag indicating duplicate/reprint copy"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> ReceiptPreviewOut:
    """Retrieve formatted receipt preview and HTML for frontend display."""
    try:
        return ReceiptService.get_receipt_preview(db, bill_id=bill_id, is_reprint=is_reprint)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{bill_id}/receipt/print-audit",
    response_model=ReceiptPrintAuditResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Receipt Print Audit (Staff & Owner)",
    description=(
        "Record an immutable audit log entry when a receipt is printed or reprinted. "
        "Does not modify financial totals or inventory."
    ),
)
@router.post(
    "/{bill_id}/receipt/print",
    response_model=ReceiptPrintAuditResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Receipt Print Audit (Alias)",
    description="Alias route for receipt print audit logging.",
)
def record_receipt_print_audit(
    bill_id: UUID,
    audit_in: ReceiptPrintAuditRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> ReceiptPrintAuditResponse:
    """Record receipt print or reprint event in audit logs."""
    client_ip = request.client.host if request.client else None
    try:
        audit = ReceiptService.record_print_audit(
            db=db,
            bill_id=bill_id,
            user_id=current_user.id,
            is_reprint=audit_in.is_reprint,
            ip_address=client_ip,
        )
        return ReceiptPrintAuditResponse(
            bill_id=bill_id,
            bill_number=str(audit.new_values.get("bill_number", "")) if audit.new_values else "",
            action=audit.action,
            printed_by_user_id=current_user.id,
            printed_at=audit.created_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{bill_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record Bill Payment (Staff & Owner)",
    description=(
        "Record a payment against a bill. Cash payments are confirmed immediately; "
        "UPI payments can be created as pending for manual verification or confirmed immediately."
    ),
)
def record_bill_payment(
    bill_id: UUID,
    payment_in: PaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> PaymentOut:
    """Record payment for a bill."""
    client_ip = request.client.host if request.client else None
    return PaymentService.record_payment(
        db=db,
        bill_id=bill_id,
        payment_in=payment_in,
        current_user=current_user,
        ip_address=client_ip,
    )


@router.get(
    "/{bill_id}/payments",
    response_model=List[PaymentOut],
    summary="Get Payments for Bill (Staff & Owner)",
    description="Retrieve all payments (pending, confirmed, rejected) recorded against this bill.",
)
def get_bill_payments(
    bill_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> List[PaymentOut]:
    """Retrieve payments for a bill."""
    return PaymentService.get_bill_payments(db, bill_id)


@router.patch(
    "/{bill_id}/cancel",
    response_model=BillOut,
    summary="Cancel Sales Bill & Restore Inventory (Owner Only)",
    description=(
        "Atomically cancel a sales bill. Restores deducted inventory quantities under row locks, "
        "records CANCELLATION stock movements, rejects unverified pending UPI payments, "
        "preserves confirmed payments for refund review, and logs an immutable audit entry."
    ),
)
def cancel_bill(
    bill_id: UUID,
    cancel_in: BillCancelRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> BillOut:
    """Cancel a bill and restore stock (Owner Only)."""
    client_ip = request.client.host if request.client else None
    return BillingService.cancel_bill(
        db=db,
        bill_id=bill_id,
        cancel_in=cancel_in,
        current_user=current_user,
        ip_address=client_ip,
    )
