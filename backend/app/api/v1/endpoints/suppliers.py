"""API endpoints for Supplier Management (Phase 5.4)."""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner, require_staff_or_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.purchase import (
    SupplierCreate,
    SupplierListResponse,
    SupplierOut,
    SupplierUpdate,
)
from app.services.purchase_service import PurchaseService

router = APIRouter()


@router.post(
    "",
    response_model=SupplierOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register New Supplier (Owner Only)",
    description="Create a new vendor profile for apparel purchase orders.",
)
def create_supplier(
    supplier_in: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> SupplierOut:
    supplier = PurchaseService.create_supplier(db, supplier_in)
    return PurchaseService.get_supplier_out(db, supplier)


@router.get(
    "",
    response_model=SupplierListResponse,
    summary="List Suppliers (Staff & Owner)",
    description="Retrieve paginated list of suppliers with live financial and purchase indicators.",
)
def list_suppliers(
    search: Optional[str] = Query(default=None, description="Search company name, contact, phone, email, GSTIN"),
    is_active: Optional[bool] = Query(default=None, description="Filter active/inactive suppliers"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> SupplierListResponse:
    items, total = PurchaseService.list_suppliers(
        db=db,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return SupplierListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{supplier_id}",
    response_model=SupplierOut,
    summary="Get Supplier Details (Staff & Owner)",
    description="Retrieve comprehensive supplier profile including outstanding liability and purchase totals.",
)
def get_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> SupplierOut:
    return PurchaseService.get_supplier_by_id(db, supplier_id)


@router.put(
    "/{supplier_id}",
    response_model=SupplierOut,
    summary="Update Supplier (Owner Only)",
    description="Modify supplier contact information, GSTIN, and address.",
)
def update_supplier(
    supplier_id: UUID,
    supplier_in: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> SupplierOut:
    supplier = PurchaseService.update_supplier(db, supplier_id, supplier_in)
    return PurchaseService.get_supplier_out(db, supplier)


@router.patch(
    "/{supplier_id}/status",
    response_model=SupplierOut,
    summary="Activate or Deactivate Supplier (Owner Only)",
    description="Toggle supplier active status. Inactive suppliers cannot be selected for new purchase orders.",
)
def set_supplier_status(
    supplier_id: UUID,
    is_active: bool = Query(..., description="Target active status (true to activate, false to deactivate)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> SupplierOut:
    supplier = PurchaseService.set_supplier_status(db, supplier_id, is_active)
    return PurchaseService.get_supplier_out(db, supplier)
