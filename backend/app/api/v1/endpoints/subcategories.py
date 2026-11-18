"""API endpoints for Subcategory catalogue management."""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner, require_staff_or_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.category import (
    SubcategoryCreate,
    SubcategoryUpdate,
    SubcategoryOut,
)
from app.services.category_service import CategoryService

router = APIRouter()


@router.post(
    "",
    response_model=SubcategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Subcategory (Owner Only)",
    description="Create a subcategory under an existing parent category.",
)
def create_subcategory(
    subcat_in: SubcategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> SubcategoryOut:
    """Create a new subcategory."""
    try:
        subcat = CategoryService.create_subcategory(db, subcat_in)
        cat = CategoryService.get_category_by_id(db, subcat.category_id)
        return SubcategoryOut(
            id=subcat.id,
            category_id=subcat.category_id,
            category_name=cat.name if cat else None,
            name=subcat.name,
            description=subcat.description,
            is_active=subcat.is_active,
            created_at=subcat.created_at,
            updated_at=subcat.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=List[SubcategoryOut],
    summary="List Subcategories (Staff & Owner)",
    description="Retrieve subcategories with optional category filter. Staff sees active only.",
)
def list_subcategories(
    category_id: Optional[UUID] = Query(default=None, description="Filter by parent category"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> List[SubcategoryOut]:
    """List subcategories."""
    active_filter = is_active
    if current_user.role == "STAFF":
        active_filter = True

    return CategoryService.list_subcategories(
        db, category_id=category_id, is_active=active_filter
    )


@router.get(
    "/{subcategory_id}",
    response_model=SubcategoryOut,
    summary="Get Subcategory by ID (Staff & Owner)",
)
def get_subcategory(
    subcategory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> SubcategoryOut:
    """Retrieve subcategory by UUID."""
    subcat = CategoryService.get_subcategory_by_id(db, subcategory_id)
    if not subcat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subcategory with ID '{subcategory_id}' was not found.",
        )
    if current_user.role == "STAFF" and not subcat.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subcategory not found or inactive.",
        )
    cat = CategoryService.get_category_by_id(db, subcat.category_id)
    return SubcategoryOut(
        id=subcat.id,
        category_id=subcat.category_id,
        category_name=cat.name if cat else None,
        name=subcat.name,
        description=subcat.description,
        is_active=subcat.is_active,
        created_at=subcat.created_at,
        updated_at=subcat.updated_at,
    )


@router.patch(
    "/{subcategory_id}",
    response_model=SubcategoryOut,
    summary="Update Subcategory (Owner Only)",
)
def update_subcategory(
    subcategory_id: UUID,
    subcat_in: SubcategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> SubcategoryOut:
    """Update subcategory attributes."""
    subcat = CategoryService.get_subcategory_by_id(db, subcategory_id)
    if not subcat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subcategory with ID '{subcategory_id}' was not found.",
        )
    try:
        updated = CategoryService.update_subcategory(db, subcat, subcat_in)
        cat = CategoryService.get_category_by_id(db, updated.category_id)
        return SubcategoryOut(
            id=updated.id,
            category_id=updated.category_id,
            category_name=cat.name if cat else None,
            name=updated.name,
            description=updated.description,
            is_active=updated.is_active,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.delete(
    "/{subcategory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Subcategory (Owner Only)",
)
def delete_subcategory(
    subcategory_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    """Delete subcategory."""
    subcat = CategoryService.get_subcategory_by_id(db, subcategory_id)
    if not subcat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subcategory with ID '{subcategory_id}' was not found.",
        )
    try:
        CategoryService.delete_subcategory(db, subcat)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
