"""Pydantic v2 schemas for store payments, UPI confirmations, and payment listings."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PaymentCreate(BaseModel):
    """Schema for recording a store counter payment (CASH or UPI)."""

    model_config = ConfigDict(extra="forbid")

    payment_method: str = Field(..., description="Payment method: 'CASH' or 'UPI'")
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Payment amount must be greater than zero")
    transaction_reference: Optional[str] = Field(
        None, max_length=100, description="UPI reference or UTR transaction ID"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Optional payment notes or remarks")
    confirm_immediately: bool = Field(
        True,
        description="Whether to confirm payment immediately (CASH and UPI default to True)",
    )

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        method = v.strip().upper()
        if method not in ("CASH", "UPI"):
            raise ValueError(f"Invalid payment method '{v}'. Only 'CASH' and 'UPI' are accepted.")
        return method

    @field_validator("transaction_reference")
    @classmethod
    def normalize_transaction_reference(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None

    @field_validator("amount")
    @classmethod
    def validate_amount_precision(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0.00"):
            raise ValueError("Payment amount must be strictly greater than zero.")
        return v.quantize(Decimal("0.01"))



class PaymentConfirmRequest(BaseModel):
    """Schema for staff confirmation of a pending UPI payment."""

    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(None, max_length=500, description="Optional confirmation notes")


class PaymentRejectRequest(BaseModel):
    """Schema for staff rejection of a pending UPI payment."""

    model_config = ConfigDict(extra="forbid")

    rejection_reason: str = Field(
        ..., min_length=3, max_length=500, description="Mandatory reason for rejecting payment"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Optional additional notes")

    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection_reason(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 3:
            raise ValueError("Rejection reason must be at least 3 characters long.")
        return cleaned


class PaymentOut(BaseModel):
    """Schema for returning payment details to client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bill_id: UUID
    payment_method: str
    amount: Decimal
    payment_status: str
    transaction_reference: Optional[str] = None
    received_by_user_id: UUID
    received_at: datetime
    confirmed_by_user_id: Optional[UUID] = None
    confirmed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Associated Bill Context (if populated)
    bill_number: Optional[str] = None
    bill_total_amount: Optional[Decimal] = None
    bill_amount_paid: Optional[Decimal] = None
    bill_balance_amount: Optional[Decimal] = None
    bill_payment_status: Optional[str] = None


class PaymentListResponse(BaseModel):
    """Paginated response for payment records."""

    model_config = ConfigDict(from_attributes=True)

    total: int
    items: List[PaymentOut]
    limit: int
    offset: int
