"""Pydantic schemas for 58mm thermal receipt generation and printing."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ReceiptStoreInfo(BaseModel):
    """Store branding and location details printed in receipt header."""

    store_name: str = "VIYON"
    tagline: Optional[str] = "MEN'S COLLECTIONS"
    address: str = "F6WR+R8W, South Rangasamuthram, North Rangasamuthram, Sathyamangalam, Tamil Nadu 638402"
    phone: str = "082702 42681"
    email: Optional[str] = None
    gstin: Optional[str] = None
    receipt_footer: Optional[str] = "Thank you for shopping at VIYON! Visit again."
    currency_code: str = "INR"
    receipt_width_mm: int = 58


class ReceiptCustomerInfo(BaseModel):
    """Customer information on receipt, or null for walk-in retail buyers."""

    id: Optional[UUID] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None


class ReceiptCashierInfo(BaseModel):
    """Staff member or owner cashier who processed the bill."""

    id: UUID
    full_name: str
    email: str


class ReceiptItemInfo(BaseModel):
    """Line item on receipt using historical snapshot data."""

    id: UUID
    product_name: str
    sku: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal


class ReceiptPaymentItem(BaseModel):
    """Individual payment record on receipt."""

    id: UUID
    payment_method: str
    amount: Decimal
    payment_status: str
    transaction_reference: Optional[str] = None
    created_at: datetime


class ReceiptPaymentBreakdown(BaseModel):
    """Comprehensive payment summary distinguishing confirmed vs pending amounts."""

    confirmed_cash: Decimal = Decimal("0.00")
    confirmed_upi: Decimal = Decimal("0.00")
    pending_upi: Decimal = Decimal("0.00")
    has_pending_upi: bool = False
    payments: List[ReceiptPaymentItem] = Field(default_factory=list)


class ReceiptCancellationDetails(BaseModel):
    """Cancellation metadata displayed when a cancelled bill is retrieved or printed."""

    cancelled_at: Optional[datetime] = None
    cancelled_by_user: Optional[str] = None
    cancellation_reason: Optional[str] = None
    refund_review_amount: Optional[Decimal] = None


class ReceiptOut(BaseModel):
    """Authoritative structured receipt data model for VIYON Billing System."""

    model_config = ConfigDict(from_attributes=True)

    bill_id: UUID
    bill_number: str
    bill_date: datetime
    created_at: datetime
    store: ReceiptStoreInfo
    customer: Optional[ReceiptCustomerInfo] = None
    cashier: ReceiptCashierInfo
    items: List[ReceiptItemInfo] = Field(default_factory=list)
    subtotal: Decimal
    item_discount_total: Decimal
    bill_discount_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    grand_total: Decimal
    amount_paid: Decimal
    balance: Decimal
    payment_method: str
    payment_status: str
    bill_status: str
    payment_breakdown: ReceiptPaymentBreakdown
    is_cancelled: bool
    cancellation_details: Optional[ReceiptCancellationDetails] = None
    is_reprint: bool = False
    raw_text: str = ""


class ReceiptPreviewOut(BaseModel):
    """Receipt preview response suitable for frontend display and thermal printing."""

    receipt_data: ReceiptOut
    formatted_text: str
    html_preview: str


class ReceiptPrintAuditRequest(BaseModel):
    """Payload to record a receipt print or reprint event."""

    is_reprint: bool = False


class ReceiptPrintAuditResponse(BaseModel):
    """Response confirming print audit log recording."""

    bill_id: UUID
    bill_number: str
    action: str
    printed_by_user_id: UUID
    printed_at: datetime
