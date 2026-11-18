"""ProductIdentifier model for global cross-table SKU and Barcode uniqueness."""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.product import Product, ProductVariant


class ProductIdentifier(Base):
    """Central registry enforcing global uniqueness for SKUs and Barcodes across products and variants."""

    __tablename__ = "product_identifiers"
    __table_args__ = (
        CheckConstraint(
            "identifier_type IN ('SKU', 'BARCODE')",
            name="ck_product_identifiers_type",
        ),
        CheckConstraint(
            "length(btrim(identifier_value)) > 0",
            name="ck_product_identifiers_value_non_empty",
        ),
        CheckConstraint(
            "((product_id IS NOT NULL AND variant_id IS NULL) OR (product_id IS NULL AND variant_id IS NOT NULL))",
            name="ck_product_identifiers_single_owner",
        ),
        UniqueConstraint(
            "identifier_type",
            "identifier_value",
            name="uq_product_identifiers_type_value",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    identifier_type: Mapped[str] = mapped_column(String(20), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    product: Mapped[Optional["Product"]] = relationship("Product", back_populates="identifiers")
    variant: Mapped[Optional["ProductVariant"]] = relationship("ProductVariant", back_populates="identifiers")

    def __repr__(self) -> str:
        owner = f"product_id={self.product_id}" if self.product_id else f"variant_id={self.variant_id}"
        return f"<ProductIdentifier type={self.identifier_type} value={self.identifier_value} {owner}>"
