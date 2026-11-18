"""Pydantic schemas for inventory levels, stock movement ledger, and threshold management."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ------------------------------------------------------------------------------
# Inventory Item Schemas
# ------------------------------------------------------------------------------
class InventoryOut(BaseModel):
    """Schema representing current real-time inventory level of a simple item or variant."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    product_name: str
    product_code: Optional[str] = None
    product_type: str
    product_image_url: Optional[str] = None
    category_id: Optional[UUID] = None
    category_name: Optional[str] = None
    subcategory_id: Optional[UUID] = None
    subcategory_name: Optional[str] = None
    variant_id: Optional[UUID] = None
    size: Optional[str] = None
    color: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    quantity: int
    low_stock_threshold: int
    is_low_stock: bool = False
    stock_status: str = "IN_STOCK"  # "IN_STOCK", "LOW_STOCK", "OUT_OF_STOCK"
    updated_at: datetime


class InventoryListResponse(BaseModel):
    """Paginated inventory listing response."""

    items: List[InventoryOut]
    total: int
    limit: int
    offset: int


class InventorySummaryOut(BaseModel):
    """Executive summary card statistics for the inventory dashboard."""

    total_products: int
    total_variants: int
    total_stock: int
    low_stock_items: int
    out_of_stock_items: int
    total_adjustments: int


# ------------------------------------------------------------------------------
# Inventory Adjustment & Inward Schemas
# ------------------------------------------------------------------------------
class InventoryAdjustmentRequest(BaseModel):
    """Request payload for manual stock adjustment."""

    product_id: UUID = Field(..., description="Target product UUID")
    variant_id: Optional[UUID] = Field(default=None, description="Target variant UUID (mandatory for VARIANT products)")
    quantity_change: int = Field(..., description="Positive integer to add, negative integer to deduct. Cannot be 0.")
    movement_type: str = Field(
        default="ADJUSTMENT",
        pattern="^(PURCHASE|ADJUSTMENT)$",
        description="Type of adjustment: PURCHASE or ADJUSTMENT",
    )
    reason: str = Field(..., min_length=2, max_length=500, description="Mandatory audit explanation for the adjustment")
    notes: Optional[str] = Field(default=None, max_length=500, description="Optional extra notes")

    @model_validator(mode="after")
    def validate_change(self) -> "InventoryAdjustmentRequest":
        if self.quantity_change == 0:
            raise ValueError("quantity_change must not be zero.")
        return self


class InventoryInwardRequest(BaseModel):
    """Request payload for stock inward (goods purchase receipt)."""

    product_id: UUID = Field(..., description="Target product UUID")
    variant_id: Optional[UUID] = Field(default=None, description="Target variant UUID (mandatory for VARIANT products)")
    quantity: int = Field(..., gt=0, description="Positive quantity received")
    purchase_reference: Optional[str] = Field(default=None, max_length=100, description="Optional PO or invoice reference")
    supplier_name: Optional[str] = Field(default=None, max_length=255, description="Optional supplier/vendor name")
    notes: Optional[str] = Field(default=None, max_length=500, description="Optional notes on the delivery")


class InventoryThresholdUpdateRequest(BaseModel):
    """Request payload to configure low-stock alert threshold for an inventory item."""

    low_stock_threshold: int = Field(..., ge=0, description="Non-negative low-stock threshold")


class InventoryAdjustmentResponse(BaseModel):
    """Response confirming successful stock adjustment or inward receipt with audit reference."""

    message: str
    product_id: UUID
    variant_id: Optional[UUID] = None
    previous_quantity: int
    quantity_change: int
    new_quantity: int
    movement_id: UUID
    movement_type: str
    reason: str
    updated_at: datetime


# ------------------------------------------------------------------------------
# Stock Movement Ledger Schemas
# ------------------------------------------------------------------------------
class StockMovementOut(BaseModel):
    """Immutable ledger record representing any inventory modification."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    product_name: Optional[str] = None
    category_name: Optional[str] = None
    variant_id: Optional[UUID] = None
    variant_size: Optional[str] = None
    variant_color: Optional[str] = None
    sku: Optional[str] = None
    movement_type: str
    quantity_change: int
    reference_type: str
    reference_id: Optional[UUID] = None
    notes: Optional[str] = None
    created_by_user_id: UUID
    created_by_user_name: Optional[str] = None
    created_at: datetime


class StockMovementListResponse(BaseModel):
    """Paginated stock movement ledger audit response."""

    items: List[StockMovementOut]
    total: int
    limit: int
    offset: int
