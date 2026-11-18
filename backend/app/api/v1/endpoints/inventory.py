"""API endpoints for real-time Inventory, Stock Inward, Adjustments, and Stock Movement ledger."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner, require_staff_or_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.inventory import (
    InventoryAdjustmentRequest,
    InventoryAdjustmentResponse,
    InventoryInwardRequest,
    InventoryListResponse,
    InventoryOut,
    InventorySummaryOut,
    InventoryThresholdUpdateRequest,
    StockMovementListResponse,
)
from app.services.inventory_service import InventoryService

router = APIRouter()


# ------------------------------------------------------------------------------
# 1. Summary Metrics Card Endpoint (Staff & Owner)
# ------------------------------------------------------------------------------
@router.get(
    "/summary",
    response_model=InventorySummaryOut,
    summary="Get Inventory Summary Metrics (Staff & Owner)",
    description="Retrieve live executive card statistics: total products, total variants, total stock, low stock, out of stock, and adjustments.",
)
def get_inventory_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> InventorySummaryOut:
    """Return inventory summary metrics."""
    return InventoryService.get_inventory_summary(db)


# ------------------------------------------------------------------------------
# 2. Low-Stock Alerts Endpoint (Staff & Owner)
# ------------------------------------------------------------------------------
@router.get(
    "/low-stock",
    response_model=InventoryListResponse,
    summary="List Low-Stock Alerts (Staff & Owner)",
    description="Retrieve inventory items where quantity is at or below the configured low-stock threshold.",
)
def list_low_stock(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> InventoryListResponse:
    """List low-stock inventory items."""
    items, total = InventoryService.list_inventory(
        db=db,
        low_stock_only=True,
        limit=limit,
        offset=offset,
    )
    return InventoryListResponse(items=items, total=total, limit=limit, offset=offset)


# ------------------------------------------------------------------------------
# 3. Stock Movement Ledger Endpoint (Staff & Owner)
# ------------------------------------------------------------------------------
@router.get(
    "/movements",
    response_model=StockMovementListResponse,
    summary="List Stock Movements (Staff & Owner)",
    description="Retrieve immutable stock ledger movements with audit details, movement type, category, and date filters.",
)
def list_stock_movements(
    product_id: Optional[UUID] = Query(default=None, description="Filter by product UUID"),
    variant_id: Optional[UUID] = Query(default=None, description="Filter by variant UUID"),
    category_id: Optional[UUID] = Query(default=None, description="Filter by category UUID"),
    user_id: Optional[UUID] = Query(default=None, description="Filter by user UUID who performed the movement"),
    movement_type: Optional[str] = Query(default=None, description="PURCHASE, SALE, RETURN, ADJUSTMENT, CANCELLATION"),
    search: Optional[str] = Query(default=None, description="Search product name, SKU, or notes"),
    start_date: Optional[datetime] = Query(default=None, description="Start timestamp"),
    end_date: Optional[datetime] = Query(default=None, description="End timestamp"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> StockMovementListResponse:
    """List stock movement ledger entries."""
    items, total = InventoryService.list_movements(
        db=db,
        product_id=product_id,
        variant_id=variant_id,
        category_id=category_id,
        user_id=user_id,
        movement_type=movement_type,
        search=search,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return StockMovementListResponse(items=items, total=total, limit=limit, offset=offset)


# ------------------------------------------------------------------------------
# 4. Inventory Listing Endpoint (Staff & Owner)
# ------------------------------------------------------------------------------
@router.get(
    "",
    response_model=InventoryListResponse,
    summary="List Inventory (Staff & Owner)",
    description="Retrieve real-time inventory levels across simple products and variants with filtering, searching, and sorting.",
)
def list_inventory(
    search: Optional[str] = Query(default=None, description="Search product name, code, SKU, or barcode"),
    product_id: Optional[UUID] = Query(default=None, description="Filter by product UUID"),
    category_id: Optional[UUID] = Query(default=None, description="Filter by category UUID"),
    subcategory_id: Optional[UUID] = Query(default=None, description="Filter by subcategory UUID"),
    stock_status: Optional[str] = Query(default=None, description="IN_STOCK, LOW_STOCK, or OUT_OF_STOCK"),
    product_type: Optional[str] = Query(default=None, description="SIMPLE or VARIANT"),
    sort_by: Optional[str] = Query(default="product_name", description="product_name, quantity, updated_at, or sku"),
    sort_desc: bool = Query(default=False, description="Sort descending if true"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> InventoryListResponse:
    """List inventory items."""
    items, total = InventoryService.list_inventory(
        db=db,
        product_id=product_id,
        category_id=category_id,
        subcategory_id=subcategory_id,
        stock_status=stock_status,
        product_type=product_type,
        low_stock_only=False,
        search=search,
        sort_by=sort_by,
        sort_desc=sort_desc,
        limit=limit,
        offset=offset,
    )
    return InventoryListResponse(items=items, total=total, limit=limit, offset=offset)


# ------------------------------------------------------------------------------
# 5. Manual Stock Adjustment (Owner Only)
# ------------------------------------------------------------------------------
@router.post(
    "/adjustments",
    response_model=InventoryAdjustmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Adjust Stock Level (Owner Only)",
    description="Atomically modify inventory with row-locking, negative stock prevention, and audit ledger tracking.",
)
def adjust_stock(
    adj_in: InventoryAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> InventoryAdjustmentResponse:
    """Adjust stock level."""
    try:
        return InventoryService.adjust_stock(db, adj_in, current_user)
    except ValueError as e:
        err_msg = str(e)
        if "Insufficient stock" in err_msg or "Cannot specify" in err_msg or "variant_id is required" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg,
            )
        if "not exist" in err_msg or "not found" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=err_msg,
        )


# ------------------------------------------------------------------------------
# 6. Stock Inward / Purchase Receipt (Owner Only)
# ------------------------------------------------------------------------------
@router.post(
    "/inward",
    response_model=InventoryAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Stock Inward / Purchase Receipt (Owner Only)",
    description="Atomically record incoming stock receipt with supplier and invoice metadata under movement type PURCHASE.",
)
def stock_inward(
    inward_in: InventoryInwardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> InventoryAdjustmentResponse:
    """Record stock inward."""
    try:
        return InventoryService.stock_inward(db, inward_in, current_user)
    except ValueError as e:
        err_msg = str(e)
        if "Cannot specify" in err_msg or "variant_id is required" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err_msg,
            )
        if "not exist" in err_msg or "not found" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=err_msg,
        )


# ------------------------------------------------------------------------------
# 7. Low-Stock Threshold Configuration (Owner Only)
# ------------------------------------------------------------------------------
@router.patch(
    "/{inventory_id}/threshold",
    response_model=InventoryOut,
    summary="Update Low-Stock Threshold (Owner Only)",
    description="Configure the low-stock alert threshold for an individual inventory item.",
)
def update_inventory_threshold(
    inventory_id: UUID,
    threshold_in: InventoryThresholdUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> InventoryOut:
    """Update inventory low-stock threshold."""
    try:
        return InventoryService.update_threshold(
            db,
            inventory_id=inventory_id,
            new_threshold=threshold_in.low_stock_threshold,
            current_owner=current_user,
        )
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


# ------------------------------------------------------------------------------
# 8. Product Inventory Details (Staff & Owner)
# ------------------------------------------------------------------------------
@router.get(
    "/{product_id}",
    response_model=List[InventoryOut],
    summary="Get Inventory by Product ID (Staff & Owner)",
    description="Retrieve stock levels for a product. Returns 1 item for SIMPLE or N items for VARIANT.",
)
def get_product_inventory(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> List[InventoryOut]:
    """Retrieve inventory for specific product."""
    items = InventoryService.get_inventory_by_product_id(db, product_id)
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No inventory records found for product ID '{product_id}'.",
        )
    return items


# ------------------------------------------------------------------------------
# 9. Stock Movement Deletion with Safe Reversal (Owner Only)
# ------------------------------------------------------------------------------
@router.delete(
    "/movements/{movement_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Stock Movement Record (Owner Only)",
    description="Owner-only endpoint to delete a stock movement record and reverse its inventory impact with negative stock prevention.",
)
def delete_stock_movement_record(
    movement_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> dict:
    """Delete a stock movement record."""
    try:
        return InventoryService.delete_stock_movement(
            db, movement_id=movement_id, current_owner=current_user
        )
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


# ------------------------------------------------------------------------------
# 10. Inventory Record Deletion (Owner Only)
# ------------------------------------------------------------------------------
@router.delete(
    "/{inventory_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Inventory Record (Owner Only)",
    description="Owner-only endpoint to delete an individual inventory record. Product and variant records remain preserved.",
)
def delete_inventory_record(
    inventory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> dict:
    """Delete an inventory record."""
    try:
        return InventoryService.delete_inventory(
            db, inventory_id=inventory_id, current_owner=current_user
        )
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
