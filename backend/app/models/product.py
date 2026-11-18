"""Product and ProductVariant models for clothing items and inventory variants."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    CheckConstraint,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Product(Base):
    """Main product catalog entity supporting simple items and items with variants."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "product_type IN ('SIMPLE', 'VARIANT')",
            name="ck_products_product_type",
        ),
        CheckConstraint(
            "base_price >= 0",
            name="ck_products_base_price_non_negative",
        ),
        CheckConstraint(
            "cost_price IS NULL OR cost_price >= 0",
            name="ck_products_cost_price_non_negative",
        ),
        # Enforces that subcategory belongs to the selected category
        ForeignKeyConstraint(
            ["subcategory_id", "category_id"],
            ["subcategories.id", "subcategories.category_id"],
            name="fk_products_subcategory_category",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    product_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
    )
    sku: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    barcode: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    product_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    sku: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
    )
    barcode: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subcategory_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    product_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    product_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="SIMPLE",
    )
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
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
    category = relationship(
        "Category",
        back_populates="products",
        foreign_keys=[category_id],
        overlaps="products,subcategory",
    )
    subcategory = relationship(
        "Subcategory",
        back_populates="products",
        foreign_keys=[subcategory_id, category_id],
        overlaps="category,products",
    )
    variants: Mapped[List["ProductVariant"]] = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    inventory = relationship("Inventory", back_populates="product")
    stock_movements = relationship("StockMovement", back_populates="product")
    identifiers = relationship("ProductIdentifier", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.product_name} type={self.product_type} price={self.base_price}>"


class ProductVariant(Base):
    """Specific clothing size and color variation with dedicated SKU and optional barcode."""

    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "size",
            "color",
            name="uq_product_variants_product_size_color",
        ),
        CheckConstraint(
            "price_override IS NULL OR price_override >= 0",
            name="ck_product_variants_price_override_non_negative",
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
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    size: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(50), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    barcode: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
    )
    price_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    inventory = relationship("Inventory", back_populates="variant")
    stock_movements = relationship("StockMovement", back_populates="variant")
    identifiers = relationship("ProductIdentifier", back_populates="variant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ProductVariant id={self.id} sku={self.sku} size={self.size} color={self.color}>"
