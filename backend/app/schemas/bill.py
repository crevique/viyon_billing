"""Pydantic schemas for sales bills, checkout cart items, and invoice responses."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from app.schemas.payment import PaymentCreate


# ------------------------------------------------------------------------------
# Bill Item Schemas
# ------------------------------------------------------------------------------
class BillItemCreate(BaseModel):
    """Schema for an item in the checkout cart."""

    product_id: UUID = Field(..., description="Target product UUID")
    variant_id: Optional[UUID] = Field(
        default=None,
        description="Target variant UUID (mandatory for VARIANT products, must be null for SIMPLE products)",
    )
    quantity: int = Field(..., gt=0, description="Positive integer quantity to purchase")
    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Optional item-level discount amount",
    )


class BillItemOut(BaseModel):
    """Immutable snapshot response schema for a purchased line item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bill_id: UUID
    product_id: Optional[UUID] = None
    variant_id: Optional[UUID] = None
    product_name_snapshot: str
    sku_snapshot: str
    size_snapshot: Optional[str] = None
    color_snapshot: Optional[str] = None
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    created_at: datetime


# ------------------------------------------------------------------------------
# Bill Header Schemas
# ------------------------------------------------------------------------------
class BillCreate(BaseModel):
    """Request payload to initiate in-store checkout and generate a bill."""

    customer_id: Optional[UUID] = Field(
        default=None,
        description="Optional registered customer UUID. Null indicates a walk-in retail customer.",
    )
    items: List[BillItemCreate] = Field(
        ...,
        min_length=1,
        description="List of product line items in the customer cart",
    )
    discount_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Overall bill-level discount amount",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional notes regarding the sale or customer",
    )
    payments: Optional[List[PaymentCreate]] = Field(
        default=None,
        description="Optional atomic counter payments (CASH or UPI) to record during checkout",
    )

    @model_validator(mode="after")
    def validate_cart(self) -> "BillCreate":
        if not self.items:
            raise ValueError("Cart cannot be empty. At least one item is required.")
        return self


class BillCancelRequest(BaseModel):
    """Schema for requesting bill cancellation (Owner Only)."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(
        ..., min_length=3, max_length=500, description="Mandatory reason for cancelling the bill"
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 3:
            raise ValueError("Cancellation reason must be at least 3 characters long.")
        return cleaned


class BillOut(BaseModel):
    """Public sales bill response schema with customer, staff, totals, and line items."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bill_number: str
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    staff_user_id: UUID
    staff_name: Optional[str] = None
    bill_date: datetime
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    balance_amount: Decimal
    payment_status: str
    bill_status: str
    notes: Optional[str] = None
    items: List[BillItemOut] = Field(default_factory=list)
    cancelled_at: Optional[datetime] = None
    cancelled_by_user_id: Optional[UUID] = None
    cancelled_by_name: Optional[str] = None
    cancellation_reason: Optional[str] = None
    refund_review_amount: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class BillListResponse(BaseModel):
    """Paginated bill listing response."""

    items: List[BillOut]
    total: int
    limit: int
    offset: int
    page: int = 1
    page_size: int = 50
    total_records: int = 0
    total_pages: int = 1
