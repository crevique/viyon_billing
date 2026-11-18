"""Expense tracking model for physical store operational costs."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    String,
    Boolean,
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


class Expense(Base):
    """Store operational expenses recorded by staff or owner."""

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(
            "payment_method IN ('CASH', 'UPI', 'CARD')",
            name="ck_expenses_payment_method",
        ),
        CheckConstraint(
            "((is_voided = TRUE AND voided_at IS NOT NULL AND void_reason IS NOT NULL) "
            "OR (is_voided = FALSE AND voided_at IS NULL AND void_reason IS NULL))",
            name="ck_expenses_void_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    expense_title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CASH",
        index=True,
    )
    expense_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    receipt_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    created_by_user = relationship("User", foreign_keys=[created_by_user_id], back_populates="expenses")
    voided_by_user = relationship("User", foreign_keys=[voided_by_user_id])

    def __repr__(self) -> str:
        return f"<Expense id={self.id} title={self.expense_title} amount={self.amount} voided={self.is_voided}>"
