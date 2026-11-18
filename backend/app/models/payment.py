"""Payment model for recording staff-confirmed cash and UPI store payments."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    String,
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

if TYPE_CHECKING:
    from app.models.bill import Bill
    from app.models.user import User


class Payment(Base):
    """Manually verified store payments (CASH and UPI) with audit and split-bill support."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "payment_method IN ('CASH', 'UPI')",
            name="ck_payments_payment_method",
        ),
        CheckConstraint(
            "payment_status IN ('PENDING', 'CONFIRMED', 'FAILED', 'REJECTED', 'REFUNDED')",
            name="ck_payments_payment_status",
        ),
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bills.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
        index=True,
    )
    transaction_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    received_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    confirmed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    bill: Mapped["Bill"] = relationship("Bill", back_populates="payments")
    received_by_user = relationship("User", foreign_keys=[received_by_user_id], back_populates="payments")
    confirmed_by_user = relationship("User", foreign_keys=[confirmed_by_user_id])

    def __repr__(self) -> str:
        return f"<Payment id={self.id} bill_id={self.bill_id} method={self.payment_method} amount={self.amount} status={self.payment_status}>"
