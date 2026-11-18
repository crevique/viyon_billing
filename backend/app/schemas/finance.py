"""Financial management, expense tracking, daily cash register, and reporting schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# 1. Expense Schemas
# ==============================================================================

class ExpenseBase(BaseModel):
    expense_title: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=Decimal("0"))
    payment_method: Literal["CASH", "UPI", "CARD"] = Field(default="CASH")
    expense_date: Optional[datetime] = None
    description: Optional[str] = None
    reference_number: Optional[str] = Field(default=None, max_length=100)
    receipt_url: Optional[str] = Field(default=None, max_length=1024)


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    expense_title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    amount: Optional[Decimal] = Field(default=None, gt=Decimal("0"))
    payment_method: Optional[Literal["CASH", "UPI", "CARD"]] = None
    expense_date: Optional[datetime] = None
    description: Optional[str] = None
    reference_number: Optional[str] = Field(default=None, max_length=100)
    receipt_url: Optional[str] = Field(default=None, max_length=1024)


class ExpenseVoidRequest(BaseModel):
    void_reason: str = Field(..., min_length=3, max_length=500)


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    expense_title: str
    category: str
    amount: Decimal
    payment_method: str
    expense_date: datetime
    description: Optional[str] = None
    reference_number: Optional[str] = None
    receipt_url: Optional[str] = None
    is_voided: bool
    voided_at: Optional[datetime] = None
    voided_by_user_id: Optional[uuid.UUID] = None
    void_reason: Optional[str] = None
    created_by_user_id: uuid.UUID
    created_by_user_name: Optional[str] = None
    voided_by_user_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ExpenseCategorySummary(BaseModel):
    category: str
    total_amount: Decimal
    count: int
    percentage: Decimal


class ExpenseListResponse(BaseModel):
    items: List[ExpenseOut]
    total: int
    page: int
    page_size: int
    total_pages: int
    total_active_amount: Decimal
    total_voided_amount: Decimal


# ==============================================================================
# 2. Daily Cash Register Schemas
# ==============================================================================

class CashOpeningRequest(BaseModel):
    business_date: Optional[date] = None
    opening_cash: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    opening_notes: Optional[str] = None


class CashMovementCreate(BaseModel):
    movement_type: Literal["INFLOW", "OUTFLOW"]
    amount: Decimal = Field(..., gt=Decimal("0"))
    reason: str = Field(..., min_length=1, max_length=255)


class CashMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    register_id: uuid.UUID
    movement_type: str
    amount: Decimal
    reason: str
    created_by_user_id: uuid.UUID
    created_by_user_name: Optional[str] = None
    created_at: datetime


class CashClosingRequest(BaseModel):
    actual_closing_cash: Decimal = Field(..., ge=Decimal("0"))
    closing_notes: Optional[str] = None


class CashCorrectionRequest(BaseModel):
    actual_closing_cash: Decimal = Field(..., ge=Decimal("0"))
    correction_reason: str = Field(..., min_length=3, max_length=500)
    closing_notes: Optional[str] = None


class DailyCashRegisterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_date: date
    opening_cash: Decimal
    opening_notes: Optional[str] = None
    opened_by_user_id: uuid.UUID
    opened_by_user_name: Optional[str] = None
    opened_at: datetime
    cash_sales: Decimal
    cash_expenses: Decimal
    other_cash_inflow: Decimal
    other_cash_outflow: Decimal
    expected_closing_cash: Decimal
    actual_closing_cash: Optional[Decimal] = None
    cash_difference: Optional[Decimal] = None
    closing_notes: Optional[str] = None
    closed_by_user_id: Optional[uuid.UUID] = None
    closed_by_user_name: Optional[str] = None
    closed_at: Optional[datetime] = None
    is_closed: bool
    is_corrected: bool
    correction_reason: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    movements: List[CashMovementOut] = []


class DailyCashRegisterListResponse(BaseModel):
    items: List[DailyCashRegisterOut]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==============================================================================
# 3. Financial Reports & Analytics Schemas
# ==============================================================================

class DailySalesSummaryOut(BaseModel):
    business_date: date
    total_bills: int
    completed_bills_count: int
    cancelled_bills_count: int
    gross_sales: Decimal
    total_item_discounts: Decimal
    total_bill_discounts: Decimal
    total_discounts: Decimal
    net_sales: Decimal
    total_tax: Decimal
    confirmed_cash_collections: Decimal
    confirmed_upi_collections: Decimal
    total_confirmed_collections: Decimal
    pending_upi_amount: Decimal
    pending_upi_count: int
    rejected_payment_amount: Decimal
    rejected_payment_count: int
    outstanding_customer_balance: Decimal


class CashFlowSummaryOut(BaseModel):
    period_start: date
    period_end: date
    opening_cash: Decimal
    cash_sales: Decimal
    other_cash_inflow: Decimal
    total_cash_inflow: Decimal
    cash_expenses: Decimal
    other_cash_outflow: Decimal
    total_cash_outflow: Decimal
    net_cash_flow: Decimal
    expected_closing_cash: Decimal
    actual_closing_cash: Optional[Decimal] = None
    cash_difference: Optional[Decimal] = None
    reconciliation_status: str


class ProfitLossReportOut(BaseModel):
    period_start: date
    period_end: date
    preset: Optional[str] = None
    revenue: Decimal
    cogs: Optional[Decimal] = None
    cogs_status: str  # COMPLETE, PARTIAL, UNAVAILABLE
    gross_profit: Optional[Decimal] = None
    gross_profit_margin_pct: Optional[Decimal] = None
    operating_expenses: Decimal
    net_operating_profit: Optional[Decimal] = None
    net_profit_margin_pct: Optional[Decimal] = None
    profit_status: str  # AVAILABLE, PARTIAL, UNAVAILABLE
    explanation_note: str
    items_sold_count: int
    items_with_cost_count: int
    items_missing_cost_count: int


class FinancialOverviewOut(BaseModel):
    period_start: date
    period_end: date
    preset: str
    net_sales: Decimal
    completed_bills_count: int
    cancelled_bills_count: int
    total_confirmed_collections: Decimal
    cash_collections: Decimal
    upi_collections: Decimal
    pending_upi_amount: Decimal
    total_operating_expenses: Decimal
    net_cash_flow: Decimal
    profit_loss: ProfitLossReportOut
    cash_register_status: Optional[str] = None


class SalesBillItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bill_number: str
    created_at: datetime
    items_count: int
    payment_method: str
    total_amount: Decimal


class SalesReportOut(BaseModel):
    period_start: date
    period_end: date
    preset: Optional[str] = None
    total_sales: Decimal = Decimal("0.00")
    completed_bills_count: int = 0
    bills: List[SalesBillItemOut] = Field(default_factory=list)
    summary: Optional[DailySalesSummaryOut] = None
    daily_trend: List[Dict[str, Any]] = Field(default_factory=list)
    category_breakdown: List[Dict[str, Any]] = Field(default_factory=list)


class ExpenseReportOut(BaseModel):
    period_start: date
    period_end: date
    preset: Optional[str] = None
    total_expenses: Decimal
    active_expenses_count: int
    voided_expenses_count: int
    by_category: List[ExpenseCategorySummary]
    by_payment_method: Dict[str, Decimal]
    expenses: List[ExpenseOut]
