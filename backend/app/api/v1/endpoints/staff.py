"""Staff Management REST API endpoints (Strictly Store Owner Protected)."""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner
from app.database.connection import get_db
from app.models.user import User
from app.schemas.user import (
    AdminPasswordReset,
    StaffActivityOut,
    StaffCreate,
    StaffMetricsOut,
    StaffUpdate,
    UserOut,
    UserStatusUpdate,
)
from app.services.staff_service import StaffService

router = APIRouter()


@router.get(
    "/metrics",
    response_model=StaffMetricsOut,
    summary="Get Staff Overview Metrics",
    description="Retrieve live counts of total staff, active staff, inactive staff, and newly registered staff this month.",
)
def get_staff_metrics(
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> StaffMetricsOut:
    """Return summary card statistics for the staff management dashboard."""
    return StaffService.get_metrics(db)


@router.get(
    "",
    response_model=List[UserOut],
    summary="List Staff Accounts",
    description="Retrieve all staff accounts with searching, active/inactive filtering, sorting, and pagination.",
)
def list_staff(
    response: Response,
    search: Optional[str] = Query(None, description="Search by name, username, phone, or email"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    role: Optional[str] = Query(None, description="Filter by role (defaults to STAFF)"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_desc: bool = Query(True, description="Sort descending if true"),
    skip: int = Query(0, ge=0, description="Records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Records per page"),
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> List[UserOut]:
    """List staff accounts with pagination metadata in X-Total-Count header."""
    staff_list, total_count = StaffService.list_staff(
        db,
        search=search,
        is_active=is_active,
        role=role,
        sort_by=sort_by,
        sort_desc=sort_desc,
        skip=skip,
        limit=limit,
    )
    response.headers["X-Total-Count"] = str(total_count)
    return [UserOut.model_validate(u) for u in staff_list]


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create Staff Account",
    description="Owner-only endpoint to create a new store cashier account with validated username and credentials.",
)
def create_staff(
    staff_in: StaffCreate,
    request: Request,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> UserOut:
    """Register a new cashier/staff account."""
    client_ip = request.client.host if request.client else None
    new_user = StaffService.create_staff(
        db, staff_in=staff_in, current_owner=current_owner, ip_address=client_ip
    )
    return UserOut.model_validate(new_user)


@router.get(
    "/{staff_id}",
    response_model=UserOut,
    summary="Get Staff Profile",
    description="Retrieve details of an individual staff member by UUID.",
)
def get_staff_details(
    staff_id: UUID,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> UserOut:
    """Get staff profile."""
    staff = StaffService.get_staff_by_id(db, staff_id)
    return UserOut.model_validate(staff)


@router.patch(
    "/{staff_id}",
    response_model=UserOut,
    summary="Update Staff Profile",
    description="Update permitted safe fields (full name, phone, email) of a staff account.",
)
def update_staff_profile(
    staff_id: UUID,
    staff_update: StaffUpdate,
    request: Request,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> UserOut:
    """Update staff profile details."""
    client_ip = request.client.host if request.client else None
    updated = StaffService.update_staff(
        db,
        staff_id=staff_id,
        staff_update=staff_update,
        current_owner=current_owner,
        ip_address=client_ip,
    )
    return UserOut.model_validate(updated)


@router.patch(
    "/{staff_id}/activate",
    response_model=UserOut,
    summary="Activate Staff Account",
    description="Activate a staff member's account, allowing them to log in and bill.",
)
def activate_staff_account(
    staff_id: UUID,
    request: Request,
    status_in: Optional[UserStatusUpdate] = None,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> UserOut:
    """Activate staff account."""
    client_ip = request.client.host if request.client else None
    reason = status_in.reason if status_in else None
    activated = StaffService.set_staff_status(
        db,
        staff_id=staff_id,
        is_active=True,
        current_owner=current_owner,
        reason=reason,
        ip_address=client_ip,
    )
    return UserOut.model_validate(activated)


@router.patch(
    "/{staff_id}/deactivate",
    response_model=UserOut,
    summary="Deactivate Staff Account",
    description="Deactivate a staff member's account. Preserves all historical bills and audit trails.",
)
def deactivate_staff_account(
    staff_id: UUID,
    request: Request,
    status_in: Optional[UserStatusUpdate] = None,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> UserOut:
    """Deactivate staff account."""
    client_ip = request.client.host if request.client else None
    reason = status_in.reason if status_in else None
    deactivated = StaffService.set_staff_status(
        db,
        staff_id=staff_id,
        is_active=False,
        current_owner=current_owner,
        reason=reason,
        ip_address=client_ip,
    )
    return UserOut.model_validate(deactivated)


@router.post(
    "/{staff_id}/reset-password",
    response_model=UserOut,
    summary="Reset Staff Password",
    description="Owner-authorized password reset for a cashier account.",
)
def reset_staff_password(
    staff_id: UUID,
    reset_in: AdminPasswordReset,
    request: Request,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> UserOut:
    """Reset staff password."""
    client_ip = request.client.host if request.client else None
    staff = StaffService.reset_password(
        db,
        staff_id=staff_id,
        reset_in=reset_in,
        current_owner=current_owner,
        ip_address=client_ip,
    )
    return UserOut.model_validate(staff)


@router.get(
    "/{staff_id}/activity",
    response_model=StaffActivityOut,
    summary="Get Staff Activity & Bills",
    description="Retrieve real transaction counts, sales volume, cancelled bills, and recent orders for a staff member.",
)
def get_staff_activity(
    staff_id: UUID,
    limit: int = Query(50, ge=1, le=100, description="Recent bills limit"),
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> StaffActivityOut:
    """Return staff activity and attributed bills."""
    return StaffService.get_staff_activity(db, staff_id=staff_id, limit=limit)


@router.delete(
    "/{staff_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove Staff Account (Owner Only)",
    description="Owner-only endpoint to remove a staff account. Deactivates and revokes access if sales history exists, or permanently deletes if clean.",
)
def remove_staff(
    staff_id: UUID,
    request: Request,
    current_owner: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    """Remove a staff account."""
    client_ip = request.client.host if request.client else None
    return StaffService.remove_staff(
        db, staff_id=staff_id, current_owner=current_owner, ip_address=client_ip
    )
