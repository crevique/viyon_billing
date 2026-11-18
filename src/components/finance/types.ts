/**
 * TypeScript Interfaces and Utilities for VIYON Financial Management, Expenses & Cash Registers
 */

export type ExpenseCategory =
  | 'RENT'
  | 'ELECTRICITY'
  | 'WATER'
  | 'INTERNET'
  | 'SALARY'
  | 'TRANSPORT'
  | 'PACKAGING'
  | 'MAINTENANCE'
  | 'SHOP_SUPPLIES'
  | 'MARKETING'
  | 'OTHER';

export type PaymentMethod = 'CASH' | 'UPI' | 'CARD';

export interface Expense {
  id: string;
  expense_title: string;
  category: string;
  amount: number | string;
  payment_method: PaymentMethod;
  expense_date: string;
  description?: string | null;
  reference_number?: string | null;
  receipt_url?: string | null;
  is_voided: boolean;
  voided_at?: string | null;
  voided_by_user_id?: string | null;
  void_reason?: string | null;
  created_by_user_id: string;
  created_by_user_name?: string | null;
  voided_by_user_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExpenseCategorySummary {
  category: string;
  total_amount: number | string;
  count: number;
  percentage: number | string;
}

export interface ExpenseListResponse {
  items: Expense[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  total_active_amount: number | string;
  total_voided_amount: number | string;
}

export interface CashMovement {
  id: string;
  register_id: string;
  movement_type: 'INFLOW' | 'OUTFLOW';
  amount: number | string;
  reason: string;
  created_by_user_id: string;
  created_by_user_name?: string | null;
  created_at: string;
}

export interface DailyCashRegister {
  id: string;
  business_date: string;
  opening_cash: number | string;
  opening_notes?: string | null;
  opened_by_user_id: string;
  opened_by_user_name?: string | null;
  opened_at: string;
  cash_sales: number | string;
  cash_expenses: number | string;
  other_cash_inflow: number | string;
  other_cash_outflow: number | string;
  expected_closing_cash: number | string;
  actual_closing_cash?: number | string | null;
  cash_difference?: number | string | null;
  closing_notes?: string | null;
  closed_by_user_id?: string | null;
  closed_by_user_name?: string | null;
  closed_at?: string | null;
  is_closed: boolean;
  is_corrected: boolean;
  correction_reason?: string | null;
  status: 'OPEN' | 'CLOSED_BALANCED' | 'CLOSED_SURPLUS' | 'CLOSED_SHORTAGE' | string;
  created_at: string;
  updated_at: string;
  movements: CashMovement[];
}

export interface DailySalesSummary {
  business_date: string;
  total_bills: number;
  completed_bills_count: number;
  cancelled_bills_count: number;
  gross_sales: number | string;
  total_item_discounts: number | string;
  total_bill_discounts: number | string;
  total_discounts: number | string;
  net_sales: number | string;
  total_tax: number | string;
  confirmed_cash_collections: number | string;
  confirmed_upi_collections: number | string;
  total_confirmed_collections: number | string;
  pending_upi_amount: number | string;
  pending_upi_count: number;
  rejected_payment_amount: number | string;
  rejected_payment_count: number;
  outstanding_customer_balance: number | string;
}

export interface ProfitLossReport {
  period_start: string;
  period_end: string;
  preset?: string | null;
  revenue: number | string;
  cogs?: number | string | null;
  cogs_status: 'COMPLETE' | 'PARTIAL' | 'UNAVAILABLE';
  gross_profit?: number | string | null;
  gross_profit_margin_pct?: number | string | null;
  operating_expenses: number | string;
  net_operating_profit?: number | string | null;
  net_profit_margin_pct?: number | string | null;
  profit_status: 'AVAILABLE' | 'PARTIAL' | 'UNAVAILABLE';
  explanation_note: string;
  items_sold_count: number;
  items_with_cost_count: number;
  items_missing_cost_count: number;
}

export interface FinancialOverview {
  period_start: string;
  period_end: string;
  preset: string;
  net_sales: number | string;
  completed_bills_count: number;
  cancelled_bills_count: number;
  total_confirmed_collections: number | string;
  cash_collections: number | string;
  upi_collections: number | string;
  pending_upi_amount: number | string;
  total_operating_expenses: number | string;
  net_cash_flow: number | string;
  profit_loss: ProfitLossReport;
  cash_register_status?: string | null;
}

/**
 * Format numerical amounts to standard Indian Currency (e.g. ₹1,25,000.00)
 */
export function formatINR(val: number | string | null | undefined): string {
  if (val === null || val === undefined || val === '') return '₹0.00';
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) return '₹0.00';

  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}
