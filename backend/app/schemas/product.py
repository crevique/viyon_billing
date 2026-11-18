"""Pydantic schemas for Product and ProductVariant catalog management."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ------------------------------------------------------------------------------
# Variant Schemas
# ------------------------------------------------------------------------------
class VariantBase(BaseModel):
    """Shared variant attributes."""

    size: str = Field(..., min_length=1, max_length=50, description="Size (e.g. S, M, L, XL, 32, 34)")
    color: str = Field(..., min_length=1, max_length=50, description="Color (e.g. Black, Navy, Olive)")
    sku: str = Field(..., min_length=1, max_length=100, description="Unique SKU for this variation")
    barcode: Optional[str] = Field(default=None, max_length=100, description="Optional unique barcode")
    price_override: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0"),
        description="Optional price override. If null, base_price is used.",
    )
    is_active: bool = Field(default=True, description="Whether variant is active")


class VariantCreate(VariantBase):
    """Schema for adding a variant to a product."""

    initial_stock: int = Field(default=0, ge=0, description="Initial inventory count for this variant")
    low_stock_threshold: int = Field(default=5, ge=0, description="Alert threshold for low inventory")


class VariantUpdate(BaseModel):
    """Schema for updating an existing variant."""

    size: Optional[str] = Field(default=None, min_length=1, max_length=50)
    color: Optional[str] = Field(default=None, min_length=1, max_length=50)
    sku: Optional[str] = Field(default=None, min_length=1, max_length=100)
    barcode: Optional[str] = Field(default=None, max_length=100)
    price_override: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    is_active: Optional[bool] = None


class VariantOut(VariantBase):
    """Public variant response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    current_stock: int = Field(default=0, description="Current available inventory")
    low_stock_threshold: int = Field(default=5, description="Low stock threshold")
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------------------
# Product Schemas
# ------------------------------------------------------------------------------
class ProductBase(BaseModel):
    """Shared product attributes."""

    product_name: str = Field(..., min_length=1, max_length=255, description="Item name")
    product_code: Optional[str] = Field(default=None, max_length=50, description="Unique product code/style code")
    category_id: UUID = Field(..., description="Parent category UUID")
    subcategory_id: Optional[UUID] = Field(default=None, description="Optional subcategory UUID")
    brand: Optional[str] = Field(default=None, max_length=100, description="Brand name")
    product_type: str = Field(default="SIMPLE", pattern="^(SIMPLE|VARIANT)$", description="SIMPLE or VARIANT")
    base_price: Decimal = Field(..., ge=Decimal("0"), description="Selling price (or base price for variants)")
    cost_price: Optional[Decimal] = Field(default=None, ge=Decimal("0"), description="Acquisition / wholesale cost price")
    description: Optional[str] = Field(default=None, description="Product description")
    product_image_url: Optional[str] = Field(default=None, max_length=1024, description="Image URL")
    is_active: bool = Field(default=True, description="Whether product is active for catalogue/sale")


class ProductCreate(ProductBase):
    """Schema for creating a new product (SIMPLE or VARIANT)."""

    # Simple Product specific fields
    sku: Optional[str] = Field(default=None, max_length=100, description="Required for SIMPLE products")
    barcode: Optional[str] = Field(default=None, max_length=100, description="Optional barcode for SIMPLE products")
    initial_stock: int = Field(default=0, ge=0, description="Initial stock for SIMPLE product")
    low_stock_threshold: int = Field(default=5, ge=0, description="Low stock threshold for SIMPLE product")

    # Variant Product specific fields
    variants: Optional[List[VariantCreate]] = Field(
        default=None,
        description="Optional initial variants for VARIANT products",
    )

    @model_validator(mode="after")
    def validate_type_and_identifiers(self) -> "ProductCreate":
        """Enforce identifier and inventory constraints based on product_type."""
        if self.product_type == "SIMPLE":
            if not self.sku or not self.sku.strip():
                raise ValueError("A valid non-empty SKU is required for SIMPLE products.")
            if self.variants:
                raise ValueError("SIMPLE products cannot have variants. Set product_type to 'VARIANT'.")
        elif self.product_type == "VARIANT":
            if self.sku or self.barcode:
                raise ValueError("VARIANT parent products must not have a top-level SKU or barcode. Define variants instead.")
        return self


class ProductUpdate(BaseModel):
    """Schema for updating an existing product."""

    product_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    product_code: Optional[str] = Field(default=None, max_length=50)
    category_id: Optional[UUID] = None
    subcategory_id: Optional[UUID] = None
    brand: Optional[str] = Field(default=None, max_length=100)
    base_price: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    cost_price: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    description: Optional[str] = None
    product_image_url: Optional[str] = Field(default=None, max_length=1024)
    sku: Optional[str] = Field(default=None, max_length=100)
    barcode: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = None


class ProductOut(ProductBase):
    """Public product response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: Optional[str] = None
    barcode: Optional[str] = None
    is_archived: bool
    category_name: Optional[str] = None
    subcategory_name: Optional[str] = None
    current_stock: Optional[int] = Field(default=0, description="Total stock or simple product stock")
    variants: List[VariantOut] = Field(default_factory=list, description="Associated variants if VARIANT type")
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Paginated product list response."""

    items: List[ProductOut]
    total: int
    limit: int
    offset: int
