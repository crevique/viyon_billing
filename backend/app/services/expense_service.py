"""Expense management service for recording, updating, voiding, and auditing store operational expenses."""

import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.models.expense import Expense
from app.models.user import User
from app.schemas.finance import (
    ExpenseCreate,
    ExpenseUpdate,
    ExpenseOut,
    ExpenseListResponse,
    ExpenseCategorySummary,
)

STORE_TZ = ZoneInfo("Asia/Kolkata")

ALLOWED_CATEGORIES = {
    "RENT",
    "ELECTRICITY",
    "WATER",
    "INTERNET",
    "SALARY",
    "TRANSPORT",
    "PACKAGING",
    "MAINTENANCE",
    "SHOP_SUPPLIES",
    "MARKETING",
    "OTHER",
}

ALLOWED_PAYMENT_METHODS = {"CASH", "UPI", "CARD"}


class ExpenseService:
    """Service handling CRUD, voiding, filtering, and summarization of store expenses."""

    @staticmethod
    def _build_expense_out(expense: Expense) -> ExpenseOut:
        """Helper to construct ExpenseOut with user display names."""
        created_name = expense.created_by_user.full_name if expense.created_by_user else None
        voided_name = expense.voided_by_user.full_name if expense.voided_by_user else None

        return ExpenseOut(
            id=expense.id,
            expense_title=expense.expense_title,
            category=expense.category,
            amount=expense.amount,
            payment_method=expense.payment_method,
            expense_date=expense.expense_date,
            description=expense.description,
            reference_number=expense.reference_number,
            receipt_url=expense.receipt_url,
            is_voided=expense.is_voided,
            voided_at=expense.voided_at,
            voided_by_user_id=expense.voided_by_user_id,
            void_reason=expense.void_reason,
            created_by_user_id=expense.created_by_user_id,
            created_by_user_name=created_name,
            voided_by_user_name=voided_name,
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )

    @classmethod
    def create_expense(
        cls,
        db: Session,
        data: ExpenseCreate,
        current_user_id: uuid.UUID,
    ) -> ExpenseOut:
        """Record a new store expense with strict validation."""
        category_clean = data.category.strip().upper()
        pm_clean = data.payment_method.strip().upper()

        if pm_clean not in ALLOWED_PAYMENT_METHODS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payment method '{data.payment_method}'. Allowed: {sorted(ALLOWED_PAYMENT_METHODS)}",
            )

        if data.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense amount must be strictly greater than zero.",
            )

        expense_dt = data.expense_date or datetime.now(timezone.utc)

        expense = Expense(
            expense_title=data.expense_title.strip(),
            category=category_clean,
            amount=Decimal(str(data.amount)),
            payment_method=pm_clean,
            expense_date=expense_dt,
            description=data.description.strip() if data.description else None,
            reference_number=data.reference_number.strip() if data.reference_number else None,
            receipt_url=data.receipt_url.strip() if data.receipt_url else None,
            created_by_user_id=current_user_id,
            is_voided=False,
        )

        db.add(expense)
        db.commit()
        db.refresh(expense)

        # Eager load creator
        creator = db.get(User, current_user_id)
        expense.created_by_user = creator

        return cls._build_expense_out(expense)

    @classmethod
    def get_expense_by_id(cls, db: Session, expense_id: uuid.UUID) -> ExpenseOut:
        """Fetch a single expense by primary key."""
        stmt = (
            select(Expense)
            .options(
                joinedload(Expense.created_by_user),
                joinedload(Expense.voided_by_user),
            )
            .where(Expense.id == expense_id)
        )
        expense = db.execute(stmt).scalars().first()
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Expense with ID '{expense_id}' was not found.",
            )
        return cls._build_expense_out(expense)

    @classmethod
    def update_expense(
        cls,
        db: Session,
        expense_id: uuid.UUID,
        data: ExpenseUpdate,
        current_user_id: uuid.UUID,
    ) -> ExpenseOut:
        """Update an existing active expense. Voided expenses cannot be modified."""
        stmt = (
            select(Expense)
            .options(
                joinedload(Expense.created_by_user),
                joinedload(Expense.voided_by_user),
            )
            .where(Expense.id == expense_id)
        )
        expense = db.execute(stmt).scalars().first()
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Expense with ID '{expense_id}' was not found.",
            )

        if expense.is_voided:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify a voided expense. Historical voided records are immutable.",
            )

        if data.expense_title is not None:
            if not data.expense_title.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Expense title cannot be empty.",
                )
            expense.expense_title = data.expense_title.strip()

        if data.category is not None:
            if not data.category.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category cannot be empty.",
                )
            expense.category = data.category.strip().upper()

        if data.amount is not None:
            if data.amount <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Expense amount must be strictly greater than zero.",
                )
            expense.amount = Decimal(str(data.amount))

        if data.payment_method is not None:
            pm_clean = data.payment_method.strip().upper()
            if pm_clean not in ALLOWED_PAYMENT_METHODS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid payment method '{data.payment_method}'. Allowed: {sorted(ALLOWED_PAYMENT_METHODS)}",
                )
            expense.payment_method = pm_clean

        if data.expense_date is not None:
            expense.expense_date = data.expense_date

        if data.description is not None:
            expense.description = data.description.strip() if data.description.strip() else None

        if data.reference_number is not None:
            expense.reference_number = data.reference_number.strip() if data.reference_number.strip() else None

        if data.receipt_url is not None:
            expense.receipt_url = data.receipt_url.strip() if data.receipt_url.strip() else None

        expense.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(expense)

        return cls._build_expense_out(expense)

    @classmethod
    def void_expense(
        cls,
        db: Session,
        expense_id: uuid.UUID,
        void_reason: str,
        current_user_id: uuid.UUID,
    ) -> ExpenseOut:
        """Void an expense with mandatory reason and audit metadata."""
        if not void_reason or not void_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid reason is required to void an expense.",
            )

        stmt = (
            select(Expense)
            .options(
                joinedload(Expense.created_by_user),
                joinedload(Expense.voided_by_user),
            )
            .where(Expense.id == expense_id)
        )
        expense = db.execute(stmt).scalars().first()
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Expense with ID '{expense_id}' was not found.",
            )

        if expense.is_voided:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense is already voided.",
            )

        expense.is_voided = True
        expense.voided_at = datetime.now(timezone.utc)
        expense.voided_by_user_id = current_user_id
        expense.void_reason = void_reason.strip()
        expense.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(expense)

        # Reload relationships for names
        voider = db.get(User, current_user_id)
        expense.voided_by_user = voider

        return cls._build_expense_out(expense)

    @classmethod
    def list_expenses(
        cls,
        db: Session,
        category: Optional[str] = None,
        payment_method: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        is_voided: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "expense_date",
        sort_order: str = "desc",
    ) -> ExpenseListResponse:
        """List expenses with filtering, search, pagination, and totals summary."""
        filters = []

        if category:
            filters.append(Expense.category == category.strip().upper())

        if payment_method:
            filters.append(Expense.payment_method == payment_method.strip().upper())

        if is_voided is not None:
            filters.append(Expense.is_voided == is_voided)

        if start_date:
            filters.append(Expense.expense_date >= start_date)

        if end_date:
            filters.append(Expense.expense_date <= end_date)

        if search and search.strip():
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Expense.expense_title.ilike(term),
                    Expense.reference_number.ilike(term),
                    Expense.description.ilike(term),
                )
            )

        # Count total matching records
        count_stmt = select(func.count(Expense.id))
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = db.scalar(count_stmt) or 0

        # Calculate totals across the filtered criteria
        active_sum_stmt = select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
            and_(*(filters + [Expense.is_voided == False]))
        )
        total_active_amount = db.scalar(active_sum_stmt) or Decimal("0.00")

        voided_sum_stmt = select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
            and_(*(filters + [Expense.is_voided == True]))
        )
        total_voided_amount = db.scalar(voided_sum_stmt) or Decimal("0.00")

        # Determine ordering
        order_col = Expense.expense_date
        if sort_by == "amount":
            order_col = Expense.amount
        elif sort_by == "created_at":
            order_col = Expense.created_at
        elif sort_by == "expense_title":
            order_col = Expense.expense_title

        order_fn = desc if sort_order.lower() == "desc" else asc

        # Paginated items query
        offset = (page - 1) * page_size
        items_stmt = (
            select(Expense)
            .options(
                joinedload(Expense.created_by_user),
                joinedload(Expense.voided_by_user),
            )
        )
        if filters:
            items_stmt = items_stmt.where(and_(*filters))
        items_stmt = (
            items_stmt
            .order_by(order_fn(order_col), desc(Expense.created_at))
            .offset(offset)
            .limit(page_size)
        )
        expenses = db.execute(items_stmt).scalars().all()

        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return ExpenseListResponse(
            items=[cls._build_expense_out(e) for e in expenses],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            total_active_amount=total_active_amount,
            total_voided_amount=total_voided_amount,
        )

    @classmethod
    def get_category_summary(
        cls,
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[ExpenseCategorySummary]:
        """Aggregate active expenses by category with amounts and percentages."""
        filters = [Expense.is_voided == False]
        if start_date:
            filters.append(Expense.expense_date >= start_date)
        if end_date:
            filters.append(Expense.expense_date <= end_date)

        total_active = (
            db.scalar(
                select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
                    and_(*filters)
                )
            )
            or Decimal("0.00")
        )

        stmt = (
            select(
                Expense.category,
                func.sum(Expense.amount).label("category_amount"),
                func.count(Expense.id).label("category_count"),
            )
            .where(and_(*filters))
            .group_by(Expense.category)
            .order_by(desc("category_amount"))
        )

        results = db.execute(stmt).all()
        summaries = []
        for cat, cat_amt, cat_cnt in results:
            pct = (
                (cat_amt / total_active * Decimal("100")).quantize(Decimal("0.01"))
                if total_active > 0
                else Decimal("0.00")
            )
            summaries.append(
                ExpenseCategorySummary(
                    category=cat,
                    total_amount=cat_amt,
                    count=cat_cnt,
                    percentage=pct,
                )
            )

        return summaries
