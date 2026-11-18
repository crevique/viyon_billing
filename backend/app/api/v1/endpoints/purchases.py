"""API endpoints for Purchase Orders, Goods Receiving (GRN), Supplier Payments, and Analytics (Phase 5.4)."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner, require_staff_or_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.purchase import (
    GoodsReceiptCreate,
    GoodsReceiptForPOCreate,
    GoodsReceiptListResponse,
    GoodsReceiptOut,
    PurchaseOrderCancelRequest,
    PurchaseOrderCreate,
    PurchaseOrderListResponse,
    PurchaseOrderOut,
    PurchaseOrderUpdate,
    PurchaseSummaryOut,
    SupplierPaymentConfirmRequest,
    SupplierPaymentCreate,
    SupplierPaymentListResponse,
    SupplierPaymentOut,
    SupplierPaymentRejectRequest,
)
from app.services.purchase_service import PurchaseService

router = APIRouter()


# ==============================================================================
# 1. Purchase Analytics & Summary (Owner Only)
# ==============================================================================
@router.get(
    "/summary",
    response_model=PurchaseSummaryOut,
    summary="Get Purchase Financial Summary (Owner Only)",
    description="Retrieve executive metrics: ordered value, received value, confirmed payments, pending payments, and supplier liability.",
)
def get_purchase_summary(
    date_from: Optional[datetime] = Query(default=None, description="Start date interval"),
    date_to: Optional[datetime] = Query(default=None, description="End date interval"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> PurchaseSummaryOut:
    return PurchaseService.get_purchase_summary(db, date_from=date_from, date_to=date_to)


# ==============================================================================
# 2. Purchase Orders
# ==============================================================================
@router.post(
    "",
    response_model=PurchaseOrderOut,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/orders",
    response_model=PurchaseOrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Purchase Order (Owner Only)",
    description="Create a new purchase order in DRAFT status. Does not modify inventory.",
)
def create_purchase_order(
    po_in: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> PurchaseOrderOut:
    po = PurchaseService.create_purchase_order(db, po_in, current_user)
    return PurchaseService.get_purchase_order_by_id(db, po.id)


@router.get(
    "",
    response_model=PurchaseOrderListResponse,
    include_in_schema=False,
)
@router.get(
    "/orders",
    response_model=PurchaseOrderListResponse,
    summary="List Purchase Orders (Staff & Owner)",
    description="Retrieve paginated list of purchase orders with status, date, and supplier filters.",
)
def list_purchase_orders(
    supplier_id: Optional[UUID] = Query(default=None, description="Filter by supplier UUID"),
    status_filter: Optional[str] = Query(default=None, description="DRAFT, ORDERED, PARTIALLY_RECEIVED, RECEIVED, CANCELLED"),
    search: Optional[str] = Query(default=None, description="Search PO number or supplier name"),
    date_from: Optional[datetime] = Query(default=None, description="Start date filter"),
    date_to: Optional[datetime] = Query(default=None, description="End date filter"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> PurchaseOrderListResponse:
    items, total = PurchaseService.list_purchase_orders(
        db=db,
        supplier_id=supplier_id,
        status_filter=status_filter,
        search=search,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return PurchaseOrderListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{po_id}",
    response_model=PurchaseOrderOut,
    include_in_schema=False,
)
@router.get(
    "/orders/{po_id}",
    response_model=PurchaseOrderOut,
    summary="Get Purchase Order Details (Staff & Owner)",
    description="Retrieve purchase order header, line items, and received vs pending breakdown.",
)
def get_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> PurchaseOrderOut:
    return PurchaseService.get_purchase_order_by_id(db, po_id)


@router.put(
    "/{po_id}",
    response_model=PurchaseOrderOut,
    include_in_schema=False,
)
@router.put(
    "/orders/{po_id}",
    response_model=PurchaseOrderOut,
    summary="Update DRAFT Purchase Order (Owner Only)",
    description="Modify items, quantities, and notes of an unplaced DRAFT purchase order.",
)
def update_purchase_order(
    po_id: UUID,
    po_update: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> PurchaseOrderOut:
    po = PurchaseService.update_purchase_order(db, po_id, po_update, current_user)
    return PurchaseService.get_purchase_order_by_id(db, po.id)


@router.post(
    "/{po_id}/place",
    response_model=PurchaseOrderOut,
    include_in_schema=False,
)
@router.post(
    "/orders/{po_id}/place",
    response_model=PurchaseOrderOut,
    summary="Place Purchase Order (Owner Only)",
    description="Transition order from DRAFT to ORDERED. Confirms order placement with supplier without increasing stock.",
)
def place_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> PurchaseOrderOut:
    po = PurchaseService.place_purchase_order(db, po_id, current_user)
    return PurchaseService.get_purchase_order_by_id(db, po.id)


@router.post(
    "/{po_id}/cancel",
    response_model=PurchaseOrderOut,
    include_in_schema=False,
)
@router.post(
    "/orders/{po_id}/cancel",
    response_model=PurchaseOrderOut,
    summary="Cancel Purchase Order (Owner Only)",
    description="Cancel an eligible purchase order with mandatory explanation.",
)
def cancel_purchase_order(
    po_id: UUID,
    cancel_in: PurchaseOrderCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> PurchaseOrderOut:
    po = PurchaseService.cancel_purchase_order(db, po_id, cancel_in, current_user)
    return PurchaseService.get_purchase_order_by_id(db, po.id)


@router.delete(
    "/{po_id}",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.delete(
    "/orders/{po_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Purchase Order (Owner Only)",
    description="Owner-only endpoint to safely delete an eligible purchase order without received goods or payments.",
)
def delete_purchase_order(
    po_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> dict:
    """Delete an eligible purchase order."""
    return PurchaseService.delete_purchase_order(db, po_id=po_id, current_owner=current_user)


# ==============================================================================
# 3. Goods Receiving / Stock Inward
# ==============================================================================
@router.post(
    "/{po_id}/receive",
    response_model=GoodsReceiptOut,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/orders/{po_id}/receive",
    response_model=GoodsReceiptOut,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def receive_goods_for_po(
    po_id: UUID,
    grn_in: GoodsReceiptForPOCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> GoodsReceiptOut:
    create_payload = GoodsReceiptCreate(
        purchase_order_id=po_id,
        receiving_date=grn_in.receiving_date,
        supplier_invoice_ref=grn_in.supplier_invoice_ref or grn_in.delivery_reference,
        delivery_reference=grn_in.delivery_reference or grn_in.supplier_invoice_ref,
        notes=grn_in.notes,
        items=grn_in.items,
    )
    return PurchaseService.receive_goods(db, create_payload, current_user)


@router.post(
    "/receiving",
    response_model=GoodsReceiptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Receive Goods Against Purchase Order (Owner Only)",
    description="Atomically record incoming delivery, increment physical inventory for accepted goods with row locks, and log StockMovement.",
)
def receive_goods(
    grn_in: GoodsReceiptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> GoodsReceiptOut:
    return PurchaseService.receive_goods(db, grn_in, current_user)


@router.get(
    "/receipts",
    response_model=GoodsReceiptListResponse,
    summary="List Goods Receipts (Staff & Owner)",
    description="Retrieve paginated history of goods receipts / stock inwards.",
)
def list_goods_receipts(
    po_id: Optional[UUID] = Query(default=None, description="Filter by purchase order UUID"),
    supplier_id: Optional[UUID] = Query(default=None, description="Filter by supplier UUID"),
    search: Optional[str] = Query(default=None, description="Search GRN number, invoice ref, or supplier name"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> GoodsReceiptListResponse:
    items, total = PurchaseService.list_goods_receipts(
        db=db,
        po_id=po_id,
        supplier_id=supplier_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return GoodsReceiptListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/receipts/{grn_id}",
    response_model=GoodsReceiptOut,
    summary="Get Goods Receipt Details (Staff & Owner)",
    description="Retrieve full details of an inward goods receipt note for display or browser printing.",
)
def get_goods_receipt(
    grn_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> GoodsReceiptOut:
    return PurchaseService.get_goods_receipt_by_id(db, grn_id)


# ==============================================================================
# 4. Supplier Payments
# ==============================================================================
@router.post(
    "/payments",
    response_model=SupplierPaymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record Supplier Payment (Owner Only)",
    description="Record a disbursement to a supplier. Cash is immediately confirmed; UPI/transfer/cheque defaults to PENDING.",
)
def create_supplier_payment(
    payment_in: SupplierPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> SupplierPaymentOut:
    return PurchaseService.create_supplier_payment(db, payment_in, current_user)


@router.get(
    "/payments",
    response_model=SupplierPaymentListResponse,
    summary="List Supplier Payments (Staff & Owner)",
    description="Retrieve paginated history of supplier disbursements and settlement statuses.",
)
def list_supplier_payments(
    supplier_id: Optional[UUID] = Query(default=None, description="Filter by supplier UUID"),
    po_id: Optional[UUID] = Query(default=None, description="Filter by purchase order UUID"),
    status_filter: Optional[str] = Query(default=None, description="PENDING, CONFIRMED, REJECTED"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> SupplierPaymentListResponse:
    items, total = PurchaseService.list_supplier_payments(
        db=db,
        supplier_id=supplier_id,
        po_id=po_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return SupplierPaymentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/payments/{payment_id}/confirm",
    response_model=SupplierPaymentOut,
    summary="Confirm Pending Supplier Payment (Owner Only)",
    description="Owner manually confirms a clearance of a bank transfer, UPI, or cheque payment.",
)
def confirm_supplier_payment(
    payment_id: UUID,
    confirm_in: SupplierPaymentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> SupplierPaymentOut:
    return PurchaseService.confirm_supplier_payment(db, payment_id, confirm_in, current_user)


@router.post(
    "/payments/{payment_id}/reject",
    response_model=SupplierPaymentOut,
    summary="Reject Pending Supplier Payment (Owner Only)",
    description="Owner rejects a failed or bounced supplier payment with mandatory explanation.",
)
def reject_supplier_payment(
    payment_id: UUID,
    reject_in: SupplierPaymentRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> SupplierPaymentOut:
    return PurchaseService.reject_supplier_payment(db, payment_id, reject_in, current_user)
