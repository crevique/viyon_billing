"""API endpoints for managing store operational expenses."""

import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner, get_db
from app.models.user import User
from app.schemas.finance import (
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseVoidRequest,
    ExpenseOut,
    ExpenseListResponse,
    ExpenseCategorySummary,
)
from app.services.expense_service import ExpenseService

router = APIRouter(tags=["Expenses"])


@router.post(
    "",
    response_model=ExpenseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new store expense",
)
def create_expense(
    data: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ExpenseOut:
    """Record an operational expense (Owner-only)."""
    return ExpenseService.create_expense(db, data, current_user.id)


@router.get(
    "",
    response_model=ExpenseListResponse,
    summary="List expenses with filtering, search, and pagination",
)
def list_expenses(
    category: Optional[str] = Query(None, description="Filter by category"),
    payment_method: Optional[str] = Query(None, description="Filter by payment method (CASH, UPI, CARD)"),
    start_date: Optional[datetime] = Query(None, description="Filter by starting date-time"),
    end_date: Optional[datetime] = Query(None, description="Filter by ending date-time"),
    is_voided: Optional[bool] = Query(None, description="Filter by voided state"),
    search: Optional[str] = Query(None, description="Search title, reference number, or description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("expense_date", description="Sort field: expense_date, amount, created_at, expense_title"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ExpenseListResponse:
    """List operational expenses with full audit details and totals."""
    return ExpenseService.list_expenses(
        db=db,
        category=category,
        payment_method=payment_method,
        start_date=start_date,
        end_date=end_date,
        is_voided=is_voided,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/summary",
    response_model=List[ExpenseCategorySummary],
    summary="Get aggregated expense summary by category",
)
def get_category_summary(
    start_date: Optional[datetime] = Query(None, description="Starting date-time"),
    end_date: Optional[datetime] = Query(None, description="Ending date-time"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> List[ExpenseCategorySummary]:
    """Summary of active operational costs grouped by category with percentages."""
    return ExpenseService.get_category_summary(db, start_date, end_date)


@router.get(
    "/{expense_id}",
    response_model=ExpenseOut,
    summary="Get a single expense by ID",
)
def get_expense(
    expense_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ExpenseOut:
    """Retrieve full details of an operational expense."""
    return ExpenseService.get_expense_by_id(db, expense_id)


@router.patch(
    "/{expense_id}",
    response_model=ExpenseOut,
    summary="Update an existing active expense",
)
def update_expense(
    expense_id: uuid.UUID,
    data: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ExpenseOut:
    """Update active expense details (Cannot edit voided expenses)."""
    return ExpenseService.update_expense(db, expense_id, data, current_user.id)


@router.patch(
    "/{expense_id}/void",
    response_model=ExpenseOut,
    summary="Void an expense with mandatory reason and audit metadata",
)
def void_expense(
    expense_id: uuid.UUID,
    data: ExpenseVoidRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ExpenseOut:
    """Void an expense permanently. Requires mandatory explanation reason."""
    return ExpenseService.void_expense(db, expense_id, data.void_reason, current_user.id)
