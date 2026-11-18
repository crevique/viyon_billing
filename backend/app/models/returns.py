"""Return and ReturnItem models for managing refunds and returned clothing items."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, TYPE_CHECKING
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Numeric,
    Integer,
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


class Return(Base):
    """Return order record associated with an existing bill and processed by staff."""

    __tablename__ = "returns"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'CANCELLED')",
            name="ck_returns_status",
        ),
        CheckConstraint(
            "total_refund_amount >= 0",
            name="ck_returns_refund_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    return_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bills.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    processed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    return_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    total_refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    bill: Mapped["Bill"] = relationship("Bill", back_populates="returns")
    processed_by_user = relationship("User", back_populates="processed_returns")
    items: Mapped[List["ReturnItem"]] = relationship(
        "ReturnItem",
        back_populates="return_record",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Return id={self.id} number={self.return_number} bill_id={self.bill_id} status={self.status}>"


class ReturnItem(Base):
    """Specific line item returned from an original bill item with restock tracking."""

    __tablename__ = "return_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_return_items_quantity_positive"),
        CheckConstraint(
            "refund_amount >= 0",
            name="ck_return_items_refund_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bill_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bill_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    restock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    return_record: Mapped["Return"] = relationship("Return", back_populates="items")
    bill_item = relationship("BillItem", back_populates="return_items")

    def __repr__(self) -> str:
        return f"<ReturnItem id={self.id} return_id={self.return_id} qty={self.quantity} refund={self.refund_amount}>"
