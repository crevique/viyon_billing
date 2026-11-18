"""API endpoints for Product catalogue and variant management."""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner, require_staff_or_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductOut,
    ProductListResponse,
    VariantCreate,
    VariantOut,
)
from app.services.product_service import ProductService

router = APIRouter()


# ------------------------------------------------------------------------------
# Product Endpoints
# ------------------------------------------------------------------------------
@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product (Owner Only)",
    description="Create a SIMPLE or VARIANT product with initial inventory and SKU/barcode validation.",
)
def create_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ProductOut:
    """Create a new product."""
    try:
        product = ProductService.create_product(db, product_in, current_user)
        return ProductService._build_product_out(product)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=ProductListResponse,
    summary="List Products (Staff & Owner)",
    description="Retrieve paginated products with full-text search, category, brand, and status filters.",
)
def list_products(
    search: Optional[str] = Query(default=None, description="Search name, code, SKU, or barcode"),
    category_id: Optional[UUID] = Query(default=None, description="Filter by category"),
    subcategory_id: Optional[UUID] = Query(default=None, description="Filter by subcategory"),
    brand: Optional[str] = Query(default=None, description="Filter by brand"),
    product_type: Optional[str] = Query(default=None, description="SIMPLE or VARIANT"),
    is_active: Optional[bool] = Query(default=None, description="Filter active status"),
    is_archived: Optional[bool] = Query(default=None, description="Filter archived status"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> ProductListResponse:
    """List products."""
    # Default filters: exclude archived items unless explicitly requested (e.g. is_archived=True)
    active_filter = is_active
    archived_filter = is_archived
    if archived_filter is None:
        archived_filter = False
    if current_user.role == "STAFF":
        if active_filter is None:
            active_filter = True

    items, total = ProductService.list_products(
        db=db,
        search=search,
        category_id=category_id,
        subcategory_id=subcategory_id,
        brand=brand,
        product_type=product_type,
        is_active=active_filter,
        is_archived=archived_filter,
        limit=limit,
        offset=offset,
    )
    return ProductListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{product_id}",
    response_model=ProductOut,
    summary="Get Product by ID (Staff & Owner)",
)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> ProductOut:
    """Retrieve complete product details including stock and variants."""
    product = ProductService.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found.",
        )
    if current_user.role == "STAFF" and (product.is_archived or not product.is_active):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product is inactive or archived.",
        )
    return ProductService._build_product_out(product)


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    summary="Update Product (Owner Only)",
)
def update_product(
    product_id: UUID,
    product_in: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ProductOut:
    """Update product attributes and identifiers."""
    product = ProductService.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found.",
        )
    try:
        updated = ProductService.update_product(db, product, product_in)
        return ProductService._build_product_out(updated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Product (Owner Only)",
    description="Soft-deletes/archives product if historical sales or inventory transactions exist, otherwise permanently deletes it.",
)
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    """Delete product."""
    product = ProductService.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found.",
        )
    try:
        result = ProductService.delete_product(db, product)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/{product_id}/archive",
    response_model=ProductOut,
    summary="Archive Product (Owner Only)",
    description="Soft-archive a product to prevent further sales while preserving SKUs and history.",
)
def archive_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ProductOut:
    """Archive product."""
    product = ProductService.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found.",
        )
    archived = ProductService.archive_product(db, product)
    return ProductService._build_product_out(archived)


@router.post(
    "/{product_id}/restore",
    response_model=ProductOut,
    summary="Restore Product (Owner Only)",
    description="Restore an archived product back to active catalogue status.",
)
def restore_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ProductOut:
    """Restore archived product."""
    product = ProductService.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found.",
        )
    restored = ProductService.restore_product(db, product)
    return ProductService._build_product_out(restored)


# ------------------------------------------------------------------------------
# Nested Variant Endpoints
# ------------------------------------------------------------------------------
@router.post(
    "/{product_id}/variants",
    response_model=VariantOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add Variant to Product (Owner Only)",
)
def add_variant(
    product_id: UUID,
    variant_in: VariantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> VariantOut:
    """Add a size/color variant with SKU and dedicated inventory."""
    product = ProductService.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found.",
        )
    try:
        variant = ProductService.create_variant(db, product, variant_in, current_user)
        return VariantOut(
            id=variant.id,
            product_id=variant.product_id,
            size=variant.size,
            color=variant.color,
            sku=variant.sku,
            barcode=variant.barcode,
            price_override=variant.price_override,
            is_active=variant.is_active,
            current_stock=variant_in.initial_stock,
            low_stock_threshold=variant_in.low_stock_threshold,
            created_at=variant.created_at,
            updated_at=variant.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "/{product_id}/variants",
    response_model=List[VariantOut],
    summary="Get Variants for Product (Staff & Owner)",
)
def get_product_variants(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> List[VariantOut]:
    """List all variants of a product."""
    product = ProductService.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found.",
        )
    out = ProductService._build_product_out(product)
    return out.variants
