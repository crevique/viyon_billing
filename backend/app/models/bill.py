"""Bill and BillItem models representing sales transactions and snapshot line items."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import (
    String,
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
    from app.models.customer import Customer
    from app.models.payment import Payment
    from app.models.returns import Return
    from app.models.user import User


class Bill(Base):
    """Main sales transaction header recording totals, customer, and payment state."""

    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint(
            "payment_status IN ('PENDING', 'PARTIALLY_PAID', 'PAID', 'REFUNDED')",
            name="ck_bills_payment_status",
        ),
        CheckConstraint(
            "bill_status IN ('DRAFT', 'COMPLETED', 'CANCELLED')",
            name="ck_bills_bill_status",
        ),
        CheckConstraint("subtotal >= 0", name="ck_bills_subtotal_non_negative"),
        CheckConstraint("discount_amount >= 0", name="ck_bills_discount_non_negative"),
        CheckConstraint("tax_amount >= 0", name="ck_bills_tax_non_negative"),
        CheckConstraint("total_amount >= 0", name="ck_bills_total_non_negative"),
        CheckConstraint("amount_paid >= 0", name="ck_bills_amount_paid_non_negative"),
        CheckConstraint("balance_amount >= 0", name="ck_bills_balance_non_negative"),
        CheckConstraint(
            "(bill_status = 'CANCELLED' AND cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL AND cancellation_reason IS NOT NULL) "
            "OR (bill_status <> 'CANCELLED' AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_reason IS NULL)",
            name="ck_bills_cancellation_consistency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    bill_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    staff_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    bill_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    balance_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
        index=True,
    )
    bill_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="COMPLETED",
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    customer = relationship("Customer", back_populates="bills")
    staff_user = relationship("User", foreign_keys=[staff_user_id], back_populates="bills")
    cancelled_by_user = relationship("User", foreign_keys=[cancelled_by_user_id])
    items: Mapped[List["BillItem"]] = relationship(
        "BillItem",
        back_populates="bill",
        cascade="save-update, merge",
    )
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="bill")
    returns: Mapped[List["Return"]] = relationship("Return", back_populates="bill")

    def __repr__(self) -> str:
        return f"<Bill id={self.id} number={self.bill_number} total={self.total_amount} status={self.bill_status}>"


class BillItem(Base):
    """Snapshot line item preserving purchased item state and prices forever."""

    __tablename__ = "bill_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_bill_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_bill_items_unit_price_non_negative"),
        CheckConstraint("discount_amount >= 0", name="ck_bill_items_discount_non_negative"),
        CheckConstraint("tax_amount >= 0", name="ck_bill_items_tax_non_negative"),
        CheckConstraint("line_total >= 0", name="ck_bill_items_line_total_non_negative"),
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
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Snapshots to guarantee historical accuracy even if products are edited or deleted
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    size_snapshot: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color_snapshot: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    bill: Mapped["Bill"] = relationship("Bill", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")
    return_items = relationship("ReturnItem", back_populates="bill_item")

    def __repr__(self) -> str:
        return f"<BillItem id={self.id} bill_id={self.bill_id} product={self.product_name_snapshot} qty={self.quantity}>"
