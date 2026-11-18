"""API endpoints for direct Variant management."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_owner, require_staff_or_owner
from app.database.connection import get_db
from app.models.product import ProductVariant
from app.models.user import User
from app.schemas.product import VariantUpdate, VariantOut
from app.services.product_service import ProductService

router = APIRouter()


@router.get(
    "/{variant_id}",
    response_model=VariantOut,
    summary="Get Variant by ID (Staff & Owner)",
)
def get_variant(
    variant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> VariantOut:
    """Retrieve variant details by UUID."""
    variant = db.scalar(
        select(ProductVariant)
        .where(ProductVariant.id == variant_id)
        .options(joinedload(ProductVariant.inventory))
    )
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID '{variant_id}' was not found.",
        )
    stock = 0
    threshold = 5
    if variant.inventory:
        inv = variant.inventory[0] if isinstance(variant.inventory, list) and variant.inventory else variant.inventory
        stock = inv.quantity
        threshold = inv.low_stock_threshold

    return VariantOut(
        id=variant.id,
        product_id=variant.product_id,
        size=variant.size,
        color=variant.color,
        sku=variant.sku,
        barcode=variant.barcode,
        price_override=variant.price_override,
        is_active=variant.is_active,
        current_stock=stock,
        low_stock_threshold=threshold,
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    )


@router.patch(
    "/{variant_id}",
    response_model=VariantOut,
    summary="Update Variant (Owner Only)",
)
def update_variant(
    variant_id: UUID,
    variant_in: VariantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> VariantOut:
    """Update variant attributes including size, color, SKU, and barcode."""
    variant = db.scalar(
        select(ProductVariant)
        .where(ProductVariant.id == variant_id)
        .options(joinedload(ProductVariant.inventory))
    )
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID '{variant_id}' was not found.",
        )
    try:
        updated = ProductService.update_variant(db, variant, variant_in)
        stock = 0
        threshold = 5
        if updated.inventory:
            inv = updated.inventory[0] if isinstance(updated.inventory, list) and updated.inventory else updated.inventory
            stock = inv.quantity
            threshold = inv.low_stock_threshold

        return VariantOut(
            id=updated.id,
            product_id=updated.product_id,
            size=updated.size,
            color=updated.color,
            sku=updated.sku,
            barcode=updated.barcode,
            price_override=updated.price_override,
            is_active=updated.is_active,
            current_stock=stock,
            low_stock_threshold=threshold,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.delete(
    "/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Variant (Owner Only)",
)
def delete_variant(
    variant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    """Delete variant if no sales history exists."""
    variant = db.scalar(
        select(ProductVariant).where(ProductVariant.id == variant_id)
    )
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with ID '{variant_id}' was not found.",
        )
    try:
        ProductService.delete_variant(db, variant)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
