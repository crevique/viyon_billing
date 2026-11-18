"""Inventory model for current stock levels and low-stock alerts."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    DateTime,
    Integer,
    ForeignKey,
    CheckConstraint,
    Index,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Inventory(Base):
    """Real-time inventory levels for simple products or specific product variants."""

    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint(
            "quantity >= 0",
            name="ck_inventory_quantity_non_negative",
        ),
        CheckConstraint(
            "low_stock_threshold >= 0",
            name="ck_inventory_threshold_non_negative",
        ),
        # Ensures exactly one inventory record per simple product (where variant_id is NULL)
        Index(
            "uq_inventory_simple_product",
            "product_id",
            unique=True,
            postgresql_where=text("variant_id IS NULL"),
        ),
        # Ensures exactly one inventory record per variant (where variant_id is NOT NULL)
        Index(
            "uq_inventory_variant",
            "variant_id",
            unique=True,
            postgresql_where=text("variant_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    product = relationship("Product", back_populates="inventory")
    variant = relationship("ProductVariant", back_populates="inventory")

    def __repr__(self) -> str:
        return f"<Inventory id={self.id} product_id={self.product_id} variant_id={self.variant_id} qty={self.quantity}>"
