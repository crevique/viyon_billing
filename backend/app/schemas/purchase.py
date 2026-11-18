"""Pydantic V2 schemas for Phase 5.4: Supplier & Purchase Management System.
Includes validation for Suppliers, Purchase Orders, Goods Receipts, Supplier Payments, and Financial Analytics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==============================================================================
# 1. Supplier Schemas
# ==============================================================================
class SupplierBase(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=200, description="Supplier company name")
    contact_person: Optional[str] = Field(default=None, max_length=100)
    phone: str = Field(..., min_length=7, max_length=20, description="Primary contact phone")
    alternate_phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=150)
    gstin: Optional[str] = Field(default=None, max_length=20, description="15-character GSTIN if applicable")
    address: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    pincode: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = Field(default=None)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 7:
            raise ValueError("Phone number must have at least 7 digits.")
        return cleaned

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        cleaned = v.strip().upper()
        if len(cleaned) != 15:
            raise ValueError("GSTIN must be exactly 15 alphanumeric characters.")
        return cleaned


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    contact_person: Optional[str] = Field(default=None, max_length=100)
    phone: Optional[str] = Field(default=None, min_length=7, max_length=20)
    alternate_phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=150)
    gstin: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    pincode: Optional[str] = Field(default=None, max_length=10)
    notes: Optional[str] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class SupplierOut(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    total_purchases: Decimal = Decimal("0.00")
    total_goods_received_value: Decimal = Decimal("0.00")
    total_paid: Decimal = Decimal("0.00")
    outstanding_balance: Decimal = Decimal("0.00")
    last_purchase_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: List[SupplierOut]
    total: int
    limit: int
    offset: int


# ==============================================================================
# 2. Purchase Order Line Item Schemas
# ==============================================================================
class PurchaseOrderItemCreate(BaseModel):
    product_id: UUID = Field(..., description="Target product UUID")
    variant_id: Optional[UUID] = Field(default=None, description="Variant UUID if variant product")
    quantity_ordered: int = Field(..., gt=0, description="Quantity ordered (> 0)")
    unit_cost: Decimal = Field(..., ge=0, description="Unit cost in INR")
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    tax_percent: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)


class PurchaseOrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    product_id: UUID
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    variant_id: Optional[UUID] = None
    size: Optional[str] = None
    color: Optional[str] = None
    sku: Optional[str] = None
    quantity_ordered: int
    quantity_received: int
    quantity_pending: int = 0
    unit_cost: Decimal
    discount_percent: Decimal
    tax_percent: Decimal
    line_total: Decimal
    created_at: datetime


# ==============================================================================
# 3. Purchase Order Schemas
# ==============================================================================
class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID = Field(..., description="Active supplier UUID")
    expected_delivery_date: Optional[datetime] = Field(default=None)
    items: List[PurchaseOrderItemCreate] = Field(..., min_length=1, description="At least one order item is required")
    notes: Optional[str] = Field(default=None)


class PurchaseOrderUpdate(BaseModel):
    expected_delivery_date: Optional[datetime] = None
    items: Optional[List[PurchaseOrderItemCreate]] = None
    notes: Optional[str] = None


class PurchaseOrderCancelRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500, description="Mandatory cancellation reason")


class PurchaseOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    po_number: str
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_phone: Optional[str] = None
    po_date: datetime
    order_date: Optional[datetime] = None
    expected_delivery_date: Optional[datetime] = None
    status: str
    subtotal: Decimal
    discount_amount: Decimal
    discount_total: Optional[Decimal] = None
    tax_amount: Decimal
    tax_total: Optional[Decimal] = None
    grand_total: Decimal
    total_amount: Optional[Decimal] = None
    total_paid: Decimal = Decimal("0.00")
    outstanding_amount: Decimal = Decimal("0.00")
    balance_due: Optional[Decimal] = None
    total_ordered_quantity: int = 0
    total_received_quantity: int = 0
    notes: Optional[str] = None
    created_by_user_id: UUID
    created_by_user_name: Optional[str] = None
    items: List[PurchaseOrderItemOut] = []
    created_at: datetime
    updated_at: datetime


class PurchaseOrderListResponse(BaseModel):
    items: List[PurchaseOrderOut]
    total: int
    limit: int
    offset: int


# ==============================================================================
# 4. Goods Receipt Note (GRN) Schemas
# ==============================================================================
class GoodsReceiptItemCreate(BaseModel):
    purchase_order_item_id: UUID = Field(..., description="Target purchase order item UUID")
    quantity_received: int = Field(..., gt=0, description="Gross quantity delivered (> 0)")
    quantity_accepted: int = Field(..., ge=0, description="Good items accepted into inventory")
    quantity_rejected: int = Field(default=0, ge=0, description="Damaged or rejected items (not added to inventory)")
    rejection_reason: Optional[str] = Field(default=None, description="Reason for rejection/damage")

    @model_validator(mode="after")
    def validate_quantities(self) -> "GoodsReceiptItemCreate":
        if self.quantity_received != (self.quantity_accepted + self.quantity_rejected):
            raise ValueError(
                f"quantity_received ({self.quantity_received}) must equal "
                f"quantity_accepted ({self.quantity_accepted}) + quantity_rejected ({self.quantity_rejected})."
            )
        if self.quantity_rejected > 0 and not self.rejection_reason:
            raise ValueError("rejection_reason is required when rejected quantity is greater than 0.")
        return self


class GoodsReceiptCreate(BaseModel):
    purchase_order_id: UUID = Field(..., description="Target Purchase Order UUID")
    receiving_date: Optional[datetime] = Field(default=None)
    supplier_invoice_ref: Optional[str] = Field(default=None, max_length=100)
    delivery_reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None)
    items: List[GoodsReceiptItemCreate] = Field(..., min_length=1, description="At least one receiving line is required")


class GoodsReceiptForPOCreate(BaseModel):
    receiving_date: Optional[datetime] = None
    supplier_invoice_ref: Optional[str] = Field(default=None, max_length=100)
    delivery_reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None)
    items: List[GoodsReceiptItemCreate] = Field(..., min_length=1, description="At least one receiving line is required")


class GoodsReceiptItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    goods_receipt_id: UUID
    purchase_order_item_id: UUID
    product_id: UUID
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    variant_id: Optional[UUID] = None
    size: Optional[str] = None
    color: Optional[str] = None
    sku: Optional[str] = None
    quantity_received: int
    quantity_accepted: int
    quantity_rejected: int
    rejection_reason: Optional[str] = None
    created_at: datetime


class GoodsReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grn_number: str
    purchase_order_id: UUID
    po_number: Optional[str] = None
    supplier_id: UUID
    supplier_name: Optional[str] = None
    receiving_date: datetime
    received_at: Optional[datetime] = None
    supplier_invoice_ref: Optional[str] = None
    delivery_reference: Optional[str] = None
    notes: Optional[str] = None
    received_by_user_id: UUID
    received_by_user_name: Optional[str] = None
    total_accepted_quantity: int
    total_rejected_quantity: int
    total_received_quantity: int = 0
    items: List[GoodsReceiptItemOut] = []
    created_at: datetime


class GoodsReceiptListResponse(BaseModel):
    items: List[GoodsReceiptOut]
    total: int
    limit: int
    offset: int


# ==============================================================================
# 5. Supplier Payment Schemas
# ==============================================================================
class SupplierPaymentCreate(BaseModel):
    supplier_id: UUID = Field(..., description="Target supplier UUID")
    purchase_order_id: Optional[UUID] = Field(default=None, description="Optional target PO UUID")
    payment_date: Optional[datetime] = Field(default=None)
    payment_method: str = Field(..., pattern="^(CASH|UPI|BANK_TRANSFER|CHEQUE)$")
    amount: Decimal = Field(..., gt=0, description="Payment amount in INR (> 0)")
    transaction_reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None)


class SupplierPaymentConfirmRequest(BaseModel):
    transaction_reference: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None)


class SupplierPaymentRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=2, max_length=500, description="Mandatory rejection reason")


class SupplierPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_number: str
    supplier_id: UUID
    supplier_name: Optional[str] = None
    purchase_order_id: Optional[UUID] = None
    po_number: Optional[str] = None
    payment_date: datetime
    payment_method: str
    amount: Decimal
    status: str
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    confirmed_by_user_id: Optional[UUID] = None
    confirmed_by_user_name: Optional[str] = None
    created_by_user_id: UUID
    created_by_user_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SupplierPaymentListResponse(BaseModel):
    items: List[SupplierPaymentOut]
    total: int
    limit: int
    offset: int


# ==============================================================================
# 6. Purchase Analytics & Summary Schemas
# ==============================================================================
class PurchaseSummaryOut(BaseModel):
    total_purchase_orders: int
    total_ordered_value: Decimal
    total_goods_received_value: Decimal
    total_confirmed_payments: Decimal
    total_pending_payments: Decimal
    total_supplier_outstanding: Decimal
    active_suppliers_count: int
    status_counts: Dict[str, int]
