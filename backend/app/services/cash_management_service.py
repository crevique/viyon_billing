"""Daily cash register management service for cash inflows, outflows, reconciliation, and closing."""

import math
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.models.cash_register import DailyCashRegister, CashMovement
from app.models.bill import Bill
from app.models.payment import Payment
from app.models.expense import Expense
from app.models.user import User
from app.schemas.finance import (
    CashOpeningRequest,
    CashMovementCreate,
    CashMovementOut,
    CashClosingRequest,
    CashCorrectionRequest,
    DailyCashRegisterOut,
    DailyCashRegisterListResponse,
)

STORE_TZ = ZoneInfo("Asia/Kolkata")


def get_kolkata_day_bounds(d: date) -> Tuple[datetime, datetime]:
    """Return timezone-aware start and end datetime bounds for a calendar date in Asia/Kolkata."""
    start_dt = datetime.combine(d, datetime.min.time(), tzinfo=STORE_TZ)
    end_dt = datetime.combine(d, datetime.max.time(), tzinfo=STORE_TZ)
    return start_dt, end_dt


class CashManagementService:
    """Service orchestrating physical cash register opening, tracking, closing, and reconciliation."""

    @staticmethod
    def _determine_status(register: DailyCashRegister) -> str:
        """Determine human/API status string for cash register."""
        if not register.is_closed:
            return "OPEN"
        diff = register.cash_difference or Decimal("0.00")
        if diff == Decimal("0.00"):
            return "CLOSED_BALANCED"
        elif diff > Decimal("0.00"):
            return "CLOSED_SURPLUS"
        else:
            return "CLOSED_SHORTAGE"

    @classmethod
    def _build_movement_out(cls, movement: CashMovement) -> CashMovementOut:
        """Helper to build CashMovementOut schema."""
        creator_name = movement.created_by_user.full_name if movement.created_by_user else None
        return CashMovementOut(
            id=movement.id,
            register_id=movement.register_id,
            movement_type=movement.movement_type,
            amount=movement.amount,
            reason=movement.reason,
            created_by_user_id=movement.created_by_user_id,
            created_by_user_name=creator_name,
            created_at=movement.created_at,
        )

    @classmethod
    def _build_register_out(cls, register: DailyCashRegister) -> DailyCashRegisterOut:
        """Helper to construct DailyCashRegisterOut with eager-loaded details and movements."""
        opened_name = register.opened_by_user.full_name if register.opened_by_user else None
        closed_name = register.closed_by_user.full_name if register.closed_by_user else None

        movements_out = [
            cls._build_movement_out(m) for m in (register.movements or [])
        ]

        return DailyCashRegisterOut(
            id=register.id,
            business_date=register.business_date,
            opening_cash=register.opening_cash,
            opening_notes=register.opening_notes,
            opened_by_user_id=register.opened_by_user_id,
            opened_by_user_name=opened_name,
            opened_at=register.opened_at,
            cash_sales=register.cash_sales,
            cash_expenses=register.cash_expenses,
            other_cash_inflow=register.other_cash_inflow,
            other_cash_outflow=register.other_cash_outflow,
            expected_closing_cash=register.expected_closing_cash,
            actual_closing_cash=register.actual_closing_cash,
            cash_difference=register.cash_difference,
            closing_notes=register.closing_notes,
            closed_by_user_id=register.closed_by_user_id,
            closed_by_user_name=closed_name,
            closed_at=register.closed_at,
            is_closed=register.is_closed,
            is_corrected=register.is_corrected,
            correction_reason=register.correction_reason,
            status=cls._determine_status(register),
            created_at=register.created_at,
            updated_at=register.updated_at,
            movements=movements_out,
        )

    @classmethod
    def sync_live_totals(cls, db: Session, register: DailyCashRegister) -> None:
        """Recalculate live sales, expenses, and auxiliary movements for open registers."""
        if register.is_closed:
            return  # Closed registers preserve snapshot totals

        start_dt, end_dt = get_kolkata_day_bounds(register.business_date)

        # 1. Sum confirmed cash payments for active (non-cancelled) bills
        cash_sales_stmt = (
            select(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
            .join(Bill, Bill.id == Payment.bill_id)
            .where(
                Payment.payment_method == "CASH",
                Payment.payment_status == "CONFIRMED",
                Bill.bill_status != "CANCELLED",
                Payment.received_at >= start_dt,
                Payment.received_at <= end_dt,
            )
        )
        register.cash_sales = db.scalar(cash_sales_stmt) or Decimal("0.00")

        # 2. Sum active cash expenses
        cash_expenses_stmt = (
            select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
                Expense.payment_method == "CASH",
                Expense.is_voided == False,
                Expense.expense_date >= start_dt,
                Expense.expense_date <= end_dt,
            )
        )
        register.cash_expenses = db.scalar(cash_expenses_stmt) or Decimal("0.00")

        # 3. Sum auxiliary movements for this register
        inflow_stmt = (
            select(func.coalesce(func.sum(CashMovement.amount), Decimal("0.00"))).where(
                CashMovement.register_id == register.id,
                CashMovement.movement_type == "INFLOW",
            )
        )
        register.other_cash_inflow = db.scalar(inflow_stmt) or Decimal("0.00")

        outflow_stmt = (
            select(func.coalesce(func.sum(CashMovement.amount), Decimal("0.00"))).where(
                CashMovement.register_id == register.id,
                CashMovement.movement_type == "OUTFLOW",
            )
        )
        register.other_cash_outflow = db.scalar(outflow_stmt) or Decimal("0.00")

        # 4. Compute expected closing cash:
        # Expected = Opening Cash + Cash Sales + Other Inflow - Cash Expenses - Other Outflow
        register.expected_closing_cash = (
            register.opening_cash
            + register.cash_sales
            + register.other_cash_inflow
            - register.cash_expenses
            - register.other_cash_outflow
        )

    @classmethod
    def open_register(
        cls,
        db: Session,
        data: CashOpeningRequest,
        current_user_id: uuid.UUID,
    ) -> DailyCashRegisterOut:
        """Open cash register for the specified business date (or today in Asia/Kolkata)."""
        target_date = data.business_date or datetime.now(STORE_TZ).date()

        # Prevent duplicate opening balance for the same business date
        existing = (
            db.execute(
                select(DailyCashRegister).where(DailyCashRegister.business_date == target_date)
            )
            .scalars()
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cash register for business date '{target_date}' is already open/initialized.",
            )

        if data.opening_cash < Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Opening cash balance cannot be negative.",
            )

        register = DailyCashRegister(
            business_date=target_date,
            opening_cash=Decimal(str(data.opening_cash)),
            opening_notes=data.opening_notes.strip() if data.opening_notes else None,
            opened_by_user_id=current_user_id,
            cash_sales=Decimal("0.00"),
            cash_expenses=Decimal("0.00"),
            other_cash_inflow=Decimal("0.00"),
            other_cash_outflow=Decimal("0.00"),
            expected_closing_cash=Decimal(str(data.opening_cash)),
            is_closed=False,
            is_corrected=False,
        )

        db.add(register)
        db.flush()

        # Synchronize any existing transactions already recorded on that date
        cls.sync_live_totals(db, register)
        db.commit()
        db.refresh(register)

        # Load creator relationship
        register.opened_by_user = db.get(User, current_user_id)

        return cls._build_register_out(register)

    @classmethod
    def get_register_by_date(
        cls,
        db: Session,
        business_date: Optional[date] = None,
    ) -> DailyCashRegisterOut:
        """Fetch cash register by business date, synchronizing live figures if open."""
        target_date = business_date or datetime.now(STORE_TZ).date()

        stmt = (
            select(DailyCashRegister)
            .options(
                joinedload(DailyCashRegister.opened_by_user),
                joinedload(DailyCashRegister.closed_by_user),
                joinedload(DailyCashRegister.movements).joinedload(CashMovement.created_by_user),
            )
            .where(DailyCashRegister.business_date == target_date)
        )
        register = db.execute(stmt).scalars().first()

        if not register:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No cash register found for business date '{target_date}'. Please record opening cash.",
            )

        if not register.is_closed:
            cls.sync_live_totals(db, register)
            db.commit()
            db.refresh(register)

        return cls._build_register_out(register)

    @classmethod
    def add_movement(
        cls,
        db: Session,
        register_id: uuid.UUID,
        data: CashMovementCreate,
        current_user_id: uuid.UUID,
    ) -> CashMovementOut:
        """Record an explicit auxiliary cash movement (petty cash injection or owner withdrawal)."""
        register = db.get(DailyCashRegister, register_id)
        if not register:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cash register '{register_id}' not found.",
            )

        if register.is_closed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add cash movements to a closed register. Closed registers are immutable.",
            )

        if data.amount <= Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cash movement amount must be strictly greater than zero.",
            )

        mtype = data.movement_type.strip().upper()
        if mtype not in ("INFLOW", "OUTFLOW"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Movement type must be 'INFLOW' or 'OUTFLOW'.",
            )

        movement = CashMovement(
            register_id=register.id,
            movement_type=mtype,
            amount=Decimal(str(data.amount)),
            reason=data.reason.strip(),
            created_by_user_id=current_user_id,
        )
        db.add(movement)
        db.flush()

        # Update register figures
        cls.sync_live_totals(db, register)
        db.commit()
        db.refresh(movement)

        movement.created_by_user = db.get(User, current_user_id)
        return cls._build_movement_out(movement)

    @classmethod
    def close_register(
        cls,
        db: Session,
        register_id: uuid.UUID,
        data: CashClosingRequest,
        current_user_id: uuid.UUID,
    ) -> DailyCashRegisterOut:
        """Close the cash register for the day, locking snapshot figures and recording variance."""
        stmt = (
            select(DailyCashRegister)
            .options(
                joinedload(DailyCashRegister.opened_by_user),
                joinedload(DailyCashRegister.closed_by_user),
                joinedload(DailyCashRegister.movements).joinedload(CashMovement.created_by_user),
            )
            .where(DailyCashRegister.id == register_id)
        )
        register = db.execute(stmt).scalars().first()
        if not register:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cash register '{register_id}' not found.",
            )

        if register.is_closed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cash register is already closed.",
            )

        if data.actual_closing_cash < Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Actual closing cash cannot be negative.",
            )

        # 1. Final live totals sync
        cls.sync_live_totals(db, register)

        # 2. Record physical count and discrepancy
        actual = Decimal(str(data.actual_closing_cash))
        difference = actual - register.expected_closing_cash

        register.actual_closing_cash = actual
        register.cash_difference = difference
        register.is_closed = True
        register.closed_at = datetime.now(timezone.utc)
        register.closed_by_user_id = current_user_id
        if data.closing_notes:
            register.closing_notes = data.closing_notes.strip()

        db.commit()
        db.refresh(register)

        register.closed_by_user = db.get(User, current_user_id)
        return cls._build_register_out(register)

    @classmethod
    def correct_closed_register(
        cls,
        db: Session,
        register_id: uuid.UUID,
        data: CashCorrectionRequest,
        current_user_id: uuid.UUID,
    ) -> DailyCashRegisterOut:
        """Owner-only workflow to correct physical count on an already-closed register."""
        if not data.correction_reason or not data.correction_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid explanation reason is strictly required to correct a closed cash register.",
            )

        stmt = (
            select(DailyCashRegister)
            .options(
                joinedload(DailyCashRegister.opened_by_user),
                joinedload(DailyCashRegister.closed_by_user),
                joinedload(DailyCashRegister.movements).joinedload(CashMovement.created_by_user),
            )
            .where(DailyCashRegister.id == register_id)
        )
        register = db.execute(stmt).scalars().first()
        if not register:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cash register '{register_id}' not found.",
            )

        if not register.is_closed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot execute correction on an open register. Use standard close workflow.",
            )

        if data.actual_closing_cash < Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Actual closing cash cannot be negative.",
            )

        actual = Decimal(str(data.actual_closing_cash))
        diff = actual - register.expected_closing_cash

        register.actual_closing_cash = actual
        register.cash_difference = diff
        register.is_corrected = True
        register.correction_reason = data.correction_reason.strip()
        if data.closing_notes:
            register.closing_notes = data.closing_notes.strip()

        db.commit()
        db.refresh(register)

        return cls._build_register_out(register)

    @classmethod
    def list_register_history(
        cls,
        db: Session,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> DailyCashRegisterListResponse:
        """List historical registers with pagination and date range filtering."""
        filters = []
        if start_date:
            filters.append(DailyCashRegister.business_date >= start_date)
        if end_date:
            filters.append(DailyCashRegister.business_date <= end_date)

        total_stmt = select(func.count(DailyCashRegister.id))
        if filters:
            total_stmt = total_stmt.where(and_(*filters))
        total = db.scalar(total_stmt) or 0

        offset = (page - 1) * page_size
        items_stmt = (
            select(DailyCashRegister)
            .options(
                joinedload(DailyCashRegister.opened_by_user),
                joinedload(DailyCashRegister.closed_by_user),
                joinedload(DailyCashRegister.movements).joinedload(CashMovement.created_by_user),
            )
        )
        if filters:
            items_stmt = items_stmt.where(and_(*filters))
        items_stmt = (
            items_stmt
            .order_by(desc(DailyCashRegister.business_date))
            .offset(offset)
            .limit(page_size)
        )
        registers = db.execute(items_stmt).scalars().unique().all()
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        return DailyCashRegisterListResponse(
            items=[cls._build_register_out(r) for r in registers],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
