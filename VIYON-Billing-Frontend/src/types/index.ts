// ==============================================================================
// VIYON BILLING FRONTEND - TYPE DEFINITIONS
// Direct 1:1 alignment with FastAPI backend Pydantic models
// ==============================================================================

// --- Authentication & User Models ---
export type UserRole = 'OWNER' | 'STAFF' | 'ADMIN' | 'CUSTOMER';

export interface User {
  id: string;
  employee_id?: string;
  full_name: string;
  username?: string;
  email: string;
  phone?: string;
  role: UserRole;
  is_active: boolean;
  last_login_at?: string;
  created_at: string;
  updated_at: string;
}

export interface LoginPayload {
  username?: string;
  email?: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
  user: User;
}

export interface StaffCreatePayload {
  full_name: string;
  username?: string;
  email?: string;
  phone?: string;
  password: string;
  confirm_password?: string;
  role: 'STAFF';
}

export interface StaffUpdatePayload {
  full_name?: string;
  phone?: string;
  email?: string;
}

export interface StaffMetrics {
  total_staff: number;
  active_staff: number;
  inactive_staff: number;
  created_this_month: number;
}

export interface StaffActivityBill {
  id: string;
  bill_number: string;
  created_at: string;
  total_amount: number | string;
  amount_paid: number | string;
  balance_amount: number | string;
  payment_status: string;
  bill_status: string;
  is_cancelled: boolean;
}

export interface StaffActivity {
  staff_id: string;
  employee_id: string;
  full_name: string;
  username?: string;
  email: string;
  phone?: string;
  role: string;
  is_active: boolean;
  date_joined: string;
  last_login_at?: string;
  total_bills_count: number;
  completed_bills_count: number;
  cancelled_bills_count: number;
  confirmed_sales_total: number | string;
  recent_bills: StaffActivityBill[];
}

// --- Category & Subcategory Models ---
export interface Category {
  id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  subcategories_count?: number;
  products_count?: number;
}

export interface Subcategory {
  id: string;
  category_id: string;
  name: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// --- Product & Variant Models ---
export interface ProductVariant {
  id: string;
  product_id: string;
  size: string;
  color: string;
  sku: string;
  barcode?: string;
  price_override?: number | string;
  is_active: boolean;
  current_stock: number;
  low_stock_threshold: number;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: string;
  product_name: string;
  product_code?: string;
  category_id: string;
  subcategory_id?: string;
  category_name?: string;
  subcategory_name?: string;
  brand?: string;
  product_type: 'SIMPLE' | 'VARIANT';
  base_price: number | string;
  cost_price?: number | string;
  description?: string;
  product_image_url?: string;
  is_active: boolean;
  is_archived: boolean;
  sku?: string;
  barcode?: string;
  current_stock: number;
  variants: ProductVariant[];
  created_at: string;
  updated_at: string;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProductCreatePayload {
  product_name: string;
  product_code?: string;
  category_id: string;
  subcategory_id?: string;
  brand?: string;
  product_type: 'SIMPLE' | 'VARIANT';
  base_price: number;
  cost_price?: number;
  description?: string;
  product_image_url?: string;
  is_active?: boolean;
  sku?: string;
  barcode?: string;
  initial_stock?: number;
  low_stock_threshold?: number;
  variants?: Array<{
    size: string;
    color: string;
    sku: string;
    barcode?: string;
    price_override?: number;
    initial_stock: number;
    low_stock_threshold: number;
    is_active?: boolean;
  }>;
}

// --- Inventory Models ---
export interface InventoryItem {
  id: string;
  product_id: string;
  product_name: string;
  product_code?: string;
  product_type: 'SIMPLE' | 'VARIANT';
  product_image_url?: string;
  category_id?: string;
  category_name?: string;
  subcategory_id?: string;
  subcategory_name?: string;
  variant_id?: string;
  size?: string;
  color?: string;
  sku?: string;
  barcode?: string;
  quantity: number;
  low_stock_threshold: number;
  is_low_stock: boolean;
  stock_status: 'IN_STOCK' | 'LOW_STOCK' | 'OUT_OF_STOCK';
  updated_at: string;
}

export interface InventorySummary {
  total_products: number;
  total_variants: number;
  total_stock: number;
  low_stock_items: number;
  out_of_stock_items: number;
  total_adjustments: number;
}

export interface StockMovement {
  id: string;
  product_id: string;
  product_name?: string;
  category_name?: string;
  variant_id?: string;
  variant_size?: string;
  variant_color?: string;
  sku?: string;
  movement_type: 'PURCHASE' | 'SALE' | 'ADJUSTMENT' | 'CANCELLATION';
  quantity_change: number;
  reference_type: string;
  reference_id?: string;
  notes?: string;
  created_by_user_id: string;
  created_by_user_name?: string;
  created_at: string;
}

export interface StockMovementListResponse {
  items: StockMovement[];
  total: number;
  limit: number;
  offset: number;
}

// --- Bill & POS Models ---
export interface BillItemCreate {
  product_id: string;
  variant_id?: string | null;
  quantity: number;
  discount_amount?: number;
}

export type BillCreateItem = BillItemCreate;

export interface BillItem {
  id: string;
  bill_id: string;
  product_id?: string;
  variant_id?: string;
  product_name_snapshot: string;
  sku_snapshot: string;
  size_snapshot?: string;
  color_snapshot?: string;
  quantity: number;
  unit_price: number | string;
  discount_amount: number | string;
  tax_amount: number | string;
  line_total: number | string;
  created_at: string;
}

export interface Bill {
  id: string;
  bill_number: string;
  customer_id?: string;
  customer_name?: string;
  customer_phone?: string;
  staff_user_id: string;
  staff_name?: string;
  bill_date: string;
  subtotal: number | string;
  discount_amount: number | string;
  tax_amount: number | string;
  total_amount: number | string;
  amount_paid: number | string;
  balance_amount: number | string;
  payment_status: 'PENDING' | 'PARTIAL' | 'PAID' | 'FAILED' | 'REJECTED';
  bill_status: 'ACTIVE' | 'COMPLETED' | 'CANCELLED';
  notes?: string;
  items: BillItem[];
  cancelled_at?: string;
  cancelled_by_user_id?: string;
  cancelled_by_name?: string;
  cancellation_reason?: string;
  refund_review_amount?: number | string;
  created_at: string;
  updated_at: string;
}

export interface BillListResponse {
  items: Bill[];
  total: number;
  limit: number;
  offset: number;
  page: number;
  page_size: number;
  total_records: number;
  total_pages: number;
}

export interface Payment {
  id: string;
  bill_id: string;
  payment_method: 'CASH' | 'UPI';
  amount: number | string;
  payment_status: 'CONFIRMED' | 'PENDING' | 'REJECTED';
  transaction_reference?: string;
  received_by_user_id: string;
  received_at: string;
  confirmed_by_user_id?: string;
  confirmed_at?: string;
  rejection_reason?: string;
  notes?: string;
  created_at: string;
  bill_number?: string;
}

export interface PaymentListResponse {
  total: number;
  items: Payment[];
  limit: number;
  offset: number;
}

// --- Thermal Receipt Models ---
export interface ReceiptStoreInfo {
  store_name: string;
  tagline?: string;
  address: string;
  phone: string;
  email?: string;
  gstin?: string;
  receipt_footer?: string;
  currency_code: string;
  receipt_width_mm: number;
}

export interface ReceiptItemInfo {
  id: string;
  product_name: string;
  sku?: string;
  size?: string;
  color?: string;
  quantity: number;
  unit_price: number | string;
  discount_amount: number | string;
  tax_amount: number | string;
  line_total: number | string;
}

export interface ReceiptPaymentItem {
  id: string;
  payment_method: string;
  amount: number | string;
  payment_status: string;
  transaction_reference?: string;
  created_at: string;
}

export interface ReceiptOut {
  bill_id: string;
  bill_number: string;
  bill_date: string;
  created_at: string;
  store: ReceiptStoreInfo;
  customer?: { id?: string; full_name?: string; phone_number?: string };
  cashier: { id: string; full_name: string; email: string };
  items: ReceiptItemInfo[];
  subtotal: number | string;
  item_discount_total: number | string;
  bill_discount_amount: number | string;
  discount_amount: number | string;
  tax_amount: number | string;
  grand_total: number | string;
  amount_paid: number | string;
  balance: number | string;
  payment_method: string;
  payment_status: string;
  bill_status: string;
  payment_breakdown: {
    confirmed_cash: number | string;
    confirmed_upi: number | string;
    pending_upi: number | string;
    has_pending_upi: boolean;
    payments: ReceiptPaymentItem[];
  };
  is_cancelled: boolean;
  cancellation_details?: {
    cancelled_at?: string;
    cancelled_by_user?: string;
    cancellation_reason?: string;
  };
  is_reprint: boolean;
  raw_text: string;
}

export interface ReceiptPreviewOut {
  receipt_data: ReceiptOut;
  formatted_text: string;
  html_preview: string;
}

// --- Supplier & Purchase Models ---
export interface Supplier {
  id: string;
  company_name: string;
  contact_person?: string;
  phone: string;
  alternate_phone?: string;
  email?: string;
  gstin?: string;
  address?: string;
  city?: string;
  state?: string;
  pincode?: string;
  notes?: string;
  is_active: boolean;
  total_purchases: number | string;
  total_goods_received_value: number | string;
  total_paid: number | string;
  outstanding_balance: number | string;
  last_purchase_date?: string;
  created_at: string;
  updated_at: string;
}

export interface SupplierListResponse {
  items: Supplier[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchaseOrderItem {
  id: string;
  purchase_order_id: string;
  product_id: string;
  product_name?: string;
  product_code?: string;
  variant_id?: string;
  size?: string;
  color?: string;
  sku?: string;
  quantity_ordered: number;
  quantity_received: number;
  quantity_pending: number;
  unit_cost: number | string;
  discount_percent: number | string;
  tax_percent: number | string;
  line_total: number | string;
  created_at: string;
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  supplier_id: string;
  supplier_name?: string;
  supplier_phone?: string;
  po_date: string;
  order_date?: string;
  expected_delivery_date?: string;
  status: 'DRAFT' | 'ORDERED' | 'PARTIALLY_RECEIVED' | 'RECEIVED' | 'CANCELLED';
  subtotal: number | string;
  discount_amount: number | string;
  tax_amount: number | string;
  grand_total: number | string;
  total_paid: number | string;
  outstanding_amount: number | string;
  total_ordered_quantity: number;
  total_received_quantity: number;
  notes?: string;
  created_by_user_id: string;
  created_by_user_name?: string;
  items: PurchaseOrderItem[];
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrderListResponse {
  items: PurchaseOrder[];
  total: number;
  limit: number;
  offset: number;
}

export interface GoodsReceiptItem {
  id: string;
  goods_receipt_id: string;
  purchase_order_item_id: string;
  product_id: string;
  product_name?: string;
  product_code?: string;
  variant_id?: string;
  size?: string;
  color?: string;
  sku?: string;
  quantity_received: number;
  quantity_accepted: number;
  quantity_rejected: number;
  rejection_reason?: string;
  created_at: string;
}

export interface GoodsReceipt {
  id: string;
  grn_number: string;
  purchase_order_id: string;
  po_number?: string;
  supplier_id: string;
  supplier_name?: string;
  receiving_date: string;
  supplier_invoice_ref?: string;
  delivery_reference?: string;
  notes?: string;
  received_by_user_id: string;
  received_by_user_name?: string;
  total_accepted_quantity: number;
  total_rejected_quantity: number;
  total_received_quantity: number;
  items: GoodsReceiptItem[];
  created_at: string;
}

export interface GoodsReceiptListResponse {
  items: GoodsReceipt[];
  total: number;
  limit: number;
  offset: number;
}

export interface GoodsReceiptPayload {
  purchase_order_id: string;
  receiving_date?: string;
  supplier_invoice_ref?: string;
  delivery_reference?: string;
  notes?: string;
  items: Array<{
    purchase_order_item_id: string;
    quantity_received: number;
    quantity_accepted: number;
    quantity_rejected: number;
    rejection_reason?: string;
  }>;
}

export interface SupplierPayment {
  id: string;
  payment_number: string;
  supplier_id: string;
  supplier_name?: string;
  purchase_order_id?: string;
  po_number?: string;
  payment_date: string;
  payment_method: 'CASH' | 'UPI' | 'BANK_TRANSFER' | 'CHEQUE';
  amount: number | string;
  status: 'CONFIRMED' | 'PENDING' | 'REJECTED';
  transaction_reference?: string;
  notes?: string;
  rejection_reason?: string;
  confirmed_at?: string;
  confirmed_by_user_name?: string;
  created_by_user_name?: string;
  created_at: string;
}

export interface SupplierPaymentListResponse {
  items: SupplierPayment[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchaseSummary {
  total_purchase_orders: number;
  total_ordered_value: number | string;
  total_goods_received_value: number | string;
  total_confirmed_payments: number | string;
  total_pending_payments: number | string;
  total_supplier_outstanding: number | string;
  active_suppliers_count: number;
  status_counts: Record<string, number>;
}

// --- Expenses & Cash Register Models ---
export interface Expense {
  id: string;
  expense_title: string;
  category: string;
  amount: number | string;
  payment_method: 'CASH' | 'UPI' | 'CARD';
  expense_date: string;
  description?: string;
  reference_number?: string;
  receipt_url?: string;
  is_voided: boolean;
  voided_at?: string;
  void_reason?: string;
  created_by_user_id: string;
  created_by_user_name?: string;
  voided_by_user_name?: string;
  created_at: string;
  updated_at: string;
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

export interface SalesBillItem {
  id: string;
  bill_number: string;
  created_at: string;
  items_count: number;
  payment_method: string;
  total_amount: number | string;
}

export interface SalesReportResponse {
  period_start: string;
  period_end: string;
  preset?: string;
  total_sales: number | string;
  completed_bills_count: number;
  bills: SalesBillItem[];
}

export interface ExpenseReportResponse {
  period_start: string;
  period_end: string;
  preset?: string;
  total_expenses: number | string;
  active_expenses_count: number;
  voided_expenses_count: number;
  expenses: Expense[];
}

export interface CashMovement {
  id: string;
  register_id: string;
  movement_type: 'INFLOW' | 'OUTFLOW';
  amount: number | string;
  reason: string;
  created_by_user_name?: string;
  created_at: string;
}

export interface DailyCashRegister {
  id: string;
  business_date: string;
  opening_cash: number | string;
  opening_notes?: string;
  opened_by_user_name?: string;
  opened_at: string;
  cash_sales: number | string;
  cash_expenses: number | string;
  other_cash_inflow: number | string;
  other_cash_outflow: number | string;
  expected_closing_cash: number | string;
  actual_closing_cash?: number | string;
  cash_difference?: number | string;
  closing_notes?: string;
  closed_by_user_name?: string;
  closed_at?: string;
  is_closed: boolean;
  is_corrected: boolean;
  status: string;
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

// --- Finance Overview Models ---
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
  cash_register_status?: string;
  profit_loss: {
    revenue: number | string;
    cogs?: number | string;
    cogs_status: string;
    gross_profit?: number | string;
    gross_profit_margin_pct?: number | string;
    operating_expenses: number | string;
    net_operating_profit?: number | string;
    net_profit_margin_pct?: number | string;
    profit_status: string;
    explanation_note: string;
    items_sold_count: number;
  };
}
