"""Daily Cash Register models for managing physical store cash movements, opening, and closing."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String,
    Boolean,
    Date,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
    CheckConstraint,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class DailyCashRegister(Base):
    """Daily cash register record tracking opening balance, cash sales/expenses, and end-of-day closing."""

    __tablename__ = "daily_cash_registers"
    __table_args__ = (
        CheckConstraint("opening_cash >= 0", name="ck_cash_registers_opening_non_negative"),
        CheckConstraint("other_cash_inflow >= 0", name="ck_cash_registers_inflow_non_negative"),
        CheckConstraint("other_cash_outflow >= 0", name="ck_cash_registers_outflow_non_negative"),
        CheckConstraint(
            "actual_closing_cash IS NULL OR actual_closing_cash >= 0",
            name="ck_cash_registers_closing_non_negative",
        ),
        CheckConstraint(
            "((is_closed = TRUE AND closed_at IS NOT NULL AND closed_by_user_id IS NOT NULL AND actual_closing_cash IS NOT NULL) "
            "OR (is_closed = FALSE AND closed_at IS NULL AND actual_closing_cash IS NULL))",
            name="ck_cash_registers_closing_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    business_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    opening_cash: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    opening_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    cash_sales: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    cash_expenses: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    other_cash_inflow: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    other_cash_outflow: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    expected_closing_cash: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    actual_closing_cash: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    cash_difference: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    closing_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correction_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    opened_by_user = relationship("User", foreign_keys=[opened_by_user_id])
    closed_by_user = relationship("User", foreign_keys=[closed_by_user_id])
    movements: Mapped[List["CashMovement"]] = relationship(
        "CashMovement",
        back_populates="register",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DailyCashRegister date={self.business_date} expected={self.expected_closing_cash} closed={self.is_closed}>"


class CashMovement(Base):
    """Explicit auxiliary cash transactions (petty cash top-up, owner withdrawal, change funds)."""

    __tablename__ = "cash_movements"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_cash_movements_amount_positive"),
        CheckConstraint(
            "movement_type IN ('INFLOW', 'OUTFLOW')",
            name="ck_cash_movements_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    register_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("daily_cash_registers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    register: Mapped["DailyCashRegister"] = relationship("DailyCashRegister", back_populates="movements")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self) -> str:
        return f"<CashMovement id={self.id} type={self.movement_type} amount={self.amount}>"
