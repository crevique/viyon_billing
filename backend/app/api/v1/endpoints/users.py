"""Staff and user management API endpoints (Owner Protected)."""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.user import (
    AdminPasswordReset,
    StaffCreate,
    UserOut,
    UserStatusUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/staff",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Staff Account",
    description="Owner-only endpoint to register a new billing staff employee.",
)
def create_staff_account(
    staff_in: StaffCreate,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> UserOut:
    """Create a new staff user with role STAFF."""
    try:
        staff_user = AuthService.create_staff(db, staff_in)
        return UserOut.model_validate(staff_user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/staff",
    response_model=List[UserOut],
    summary="List Staff Accounts",
    description="Owner-only endpoint to retrieve all store billing staff accounts.",
)
def list_staff_accounts(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> List[UserOut]:
    """List staff accounts with pagination and filtering."""
    staff_list = AuthService.list_staff(db, is_active=is_active, skip=skip, limit=limit)
    return [UserOut.model_validate(u) for u in staff_list]


@router.patch(
    "/{user_id}/status",
    response_model=UserOut,
    summary="Update User Status (Activate/Deactivate)",
    description="Owner-only endpoint to activate or deactivate a staff account.",
)
def update_user_status(
    user_id: UUID,
    status_update: UserStatusUpdate,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> UserOut:
    """Activate or deactivate user account."""
    try:
        updated_user = AuthService.update_staff_status(
            db,
            user_id=user_id,
            is_active=status_update.is_active,
            acting_user=current_owner,
        )
        return UserOut.model_validate(updated_user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{user_id}/reset-password",
    response_model=UserOut,
    summary="Admin Password Reset",
    description="Owner-only endpoint to reset a staff member's password.",
)
def admin_reset_password(
    user_id: UUID,
    reset_data: AdminPasswordReset,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> UserOut:
    """Reset a staff member's password."""
    try:
        user = AuthService.reset_password(db, user_id=user_id, new_password=reset_data.new_password)
        return UserOut.model_validate(user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
