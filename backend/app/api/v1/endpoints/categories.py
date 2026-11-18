"""API endpoints for Category and Subcategory management."""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner, require_staff_or_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryOut,
    SubcategoryOut,
)
from app.services.category_service import CategoryService

router = APIRouter()


# ------------------------------------------------------------------------------
# Category Endpoints
# ------------------------------------------------------------------------------
@router.post(
    "",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Category (Owner Only)",
    description="Create a new top-level product category with duplicate name prevention.",
)
def create_category(
    category_in: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> CategoryOut:
    """Create a new category."""
    try:
        cat = CategoryService.create_category(db, category_in)
        return CategoryOut(
            id=cat.id,
            name=cat.name,
            description=cat.description,
            is_active=cat.is_active,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
            subcategories_count=0,
            products_count=0,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "",
    response_model=List[CategoryOut],
    summary="List Categories (Staff & Owner)",
    description="Retrieve all product categories with subcategory and product counts. Staff sees active categories only.",
)
def list_categories(
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search category name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> List[CategoryOut]:
    """List product categories."""
    # Enforce active-only for STAFF users
    active_filter = is_active
    if current_user.role == "STAFF":
        active_filter = True

    return CategoryService.list_categories(db, is_active=active_filter, search=search)


@router.get(
    "/{category_id}",
    response_model=CategoryOut,
    summary="Get Category by ID (Staff & Owner)",
)
def get_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> CategoryOut:
    """Retrieve category details by UUID."""
    cat = CategoryService.get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID '{category_id}' was not found.",
        )
    # Check permissions for staff
    if current_user.role == "STAFF" and not cat.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found or inactive.",
        )
    cats = CategoryService.list_categories(db)
    for c in cats:
        if c.id == category_id:
            return c
    return CategoryOut(
        id=cat.id,
        name=cat.name,
        description=cat.description,
        is_active=cat.is_active,
        created_at=cat.created_at,
        updated_at=cat.updated_at,
    )


@router.patch(
    "/{category_id}",
    response_model=CategoryOut,
    summary="Update Category (Owner Only)",
)
def update_category(
    category_id: UUID,
    category_in: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> CategoryOut:
    """Update category attributes."""
    cat = CategoryService.get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID '{category_id}' was not found.",
        )
    try:
        updated = CategoryService.update_category(db, cat, category_in)
        return CategoryOut(
            id=updated.id,
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
    "/{category_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Category (Owner Only)",
    description="Deletes category if no subcategories or products reference it.",
)
def delete_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    """Delete category."""
    cat = CategoryService.get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID '{category_id}' was not found.",
        )
    try:
        CategoryService.delete_category(db, cat)
        return {"message": f"Category '{cat.name}' was permanently deleted."}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# ------------------------------------------------------------------------------
# Category Nested Subcategories Endpoint
# ------------------------------------------------------------------------------
@router.get(
    "/{category_id}/subcategories",
    response_model=List[SubcategoryOut],
    summary="Get Subcategories for a Category (Staff & Owner)",
)
def get_category_subcategories(
    category_id: UUID,
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_owner),
) -> List[SubcategoryOut]:
    """Retrieve all subcategories under a specific parent category."""
    cat = CategoryService.get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with ID '{category_id}' was not found.",
        )
    active_filter = is_active
    if current_user.role == "STAFF":
        active_filter = True

    return CategoryService.list_subcategories(
        db, category_id=category_id, is_active=active_filter
    )
