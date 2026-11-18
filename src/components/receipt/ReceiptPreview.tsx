import React, { useState, useEffect, useRef } from 'react';

// =============================================================================
// TypeScript Interfaces for VIYON 58mm Thermal Receipt
// =============================================================
export interface ReceiptStoreInfo {
  store_name: string;
  tagline?: string | null;
  address: string;
  phone: string;
  email?: string | null;
  gstin?: string | null;
  receipt_footer?: string | null;
  currency_code: string;
  receipt_width_mm: number;
}

export interface ReceiptCustomerInfo {
  id?: string | null;
  full_name?: string | null;
  phone_number?: string | null;
}

export interface ReceiptCashierInfo {
  id: string;
  full_name: string;
  email: string;
}

export interface ReceiptItemInfo {
  id: string;
  product_name: string;
  sku?: string | null;
  size?: string | null;
  color?: string | null;
  quantity: number;
  unit_price: string | number;
  discount_amount: string | number;
  tax_amount: string | number;
  line_total: string | number;
}

export interface ReceiptPaymentItem {
  id: string;
  payment_method: string;
  amount: string | number;
  payment_status: string;
  transaction_reference?: string | null;
  created_at: string;
}

export interface ReceiptPaymentBreakdown {
  confirmed_cash: string | number;
  confirmed_upi: string | number;
  pending_upi: string | number;
  has_pending_upi: boolean;
  payments: ReceiptPaymentItem[];
}

export interface ReceiptCancellationDetails {
  cancelled_at?: string | null;
  cancelled_by_user?: string | null;
  cancellation_reason?: string | null;
  refund_review_amount?: string | number | null;
}

export interface ReceiptData {
  bill_id: string;
  bill_number: string;
  bill_date: string;
  created_at: string;
  store: ReceiptStoreInfo;
  customer?: ReceiptCustomerInfo | null;
  cashier: ReceiptCashierInfo;
  items: ReceiptItemInfo[];
  subtotal: string | number;
  item_discount_total: string | number;
  bill_discount_amount: string | number;
  discount_amount: string | number;
  tax_amount: string | number;
  grand_total: string | number;
  amount_paid: string | number;
  balance: string | number;
  payment_method: string;
  payment_status: string;
  bill_status: string;
  payment_breakdown: ReceiptPaymentBreakdown;
  is_cancelled: boolean;
  cancellation_details?: ReceiptCancellationDetails | null;
  is_reprint?: boolean;
  raw_text?: string;
}

export interface ReceiptPreviewProps {
  billId?: string;
  billNumber?: string;
  initialReceiptData?: ReceiptData | null;
  isReprint?: boolean;
  onClose?: () => void;
  onPrintSuccess?: () => void;
  apiBaseUrl?: string;
}

// =============================================================================
// Helper formatters
// =============================================================================
const formatCurrency = (val: string | number | undefined | null): string => {
  if (val === undefined || val === null) return '₹0.00';
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) return '₹0.00';
  return `₹${num.toFixed(2)}`;
};

const formatDateTime = (isoStr: string | undefined | null): string => {
  if (!isoStr) return '';
  try {
    const dt = new Date(isoStr);
    return dt.toLocaleString('en-IN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return isoStr;
  }
};

// =============================================================================
// Main ReceiptPreview Component (SEZNIK Veer 58mm Thermal Optimized)
// =============================================================================
export const ReceiptPreview: React.FC<ReceiptPreviewProps> = ({
  billId,
  billNumber,
  initialReceiptData = null,
  isReprint = false,
  onClose,
  onPrintSuccess,
  apiBaseUrl = '/api/v1',
}) => {
  const [receipt, setReceipt] = useState<ReceiptData | null>(initialReceiptData);
  const [loading, setLoading] = useState<boolean>(!initialReceiptData);
  const [error, setError] = useState<string | null>(null);
  const [reprintMode, setReprintMode] = useState<boolean>(isReprint);
  const [isPrinting, setIsPrinting] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const receiptPrintRef = useRef<HTMLDivElement>(null);

  // Fetch receipt if not provided as initial data
  useEffect(() => {
    if (initialReceiptData) {
      setReceipt(initialReceiptData);
      setLoading(false);
      return;
    }

    if (!billId && !billNumber) {
      setError('Please provide a Bill ID or Bill Number to generate a receipt.');
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    const endpoint = billId
      ? `${apiBaseUrl}/bills/${billId}/receipt?is_reprint=${reprintMode}`
      : `${apiBaseUrl}/bills/receipt/by-number/${encodeURIComponent(billNumber || '')}?is_reprint=${reprintMode}`;

    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    const headers: Record<string, string> = {
      Accept: 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    fetch(endpoint, { headers })
      .then(async (res) => {
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to fetch receipt (Status ${res.status})`);
        }
        return res.json();
      })
      .then((data: ReceiptData) => {
        if (isMounted) {
          setReceipt(data);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (isMounted) {
          setError(err.message || 'Unable to load receipt data.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [billId, billNumber, reprintMode, apiBaseUrl, initialReceiptData]);

  // Handle native browser print
  const handlePrint = async () => {
    if (!receipt) return;
    setIsPrinting(true);

    // 1. Audit log the print / reprint action asynchronously
    try {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      const auditUrl = `${apiBaseUrl}/bills/${receipt.bill_id}/receipt/print-audit`;
      await fetch(auditUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ is_reprint: reprintMode }),
      }).catch((e) => console.warn('Print audit recording failed:', e));
    } catch (e) {
      console.warn('Audit error:', e);
    }

    // 2. Trigger native browser print dialog
    window.print();
    setIsPrinting(false);
    if (onPrintSuccess) {
      onPrintSuccess();
    }
  };

  // Copy raw 32-column monospace thermal text to clipboard
  const handleCopyRawText = () => {
    if (receipt?.raw_text) {
      navigator.clipboard.writeText(receipt.raw_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-white rounded-lg shadow-md max-w-sm mx-auto">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-900 mb-3"></div>
        <p className="text-sm font-medium text-zinc-600">Generating receipt for printing...</p>
      </div>
    );
  }

  if (error || !receipt) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-lg max-w-sm mx-auto text-center">
        <div className="text-red-600 font-semibold mb-2">Receipt Unavailable</div>
        <p className="text-xs text-red-700 mb-4">{error || 'No receipt found'}</p>
        {onClose && (
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-zinc-800 text-white text-xs font-medium rounded hover:bg-zinc-700 transition"
          >
            Close
          </button>
        )}
      </div>
    );
  }

  const {
    store,
    customer,
    cashier,
    items,
    payment_breakdown,
    cancellation_details,
    is_cancelled,
  } = receipt;

  return (
    <div className="receipt-container flex flex-col items-center max-w-md mx-auto my-4">
      {/* ===================================================================
          Print Styling Injected for 58mm SEZNIK Veer Thermal Printers
          =================================================================== */}
      <style>{`
        @page {
          size: 58mm auto;
          margin: 0;
        }
        @media print {
          body * {
            visibility: hidden;
          }
          #viyon-thermal-receipt, #viyon-thermal-receipt * {
            visibility: visible;
          }
          #viyon-thermal-receipt {
            position: absolute;
            left: 0;
            top: 0;
            width: 58mm !important;
            max-width: 58mm !important;
            padding: 2mm 3mm !important;
            margin: 0 auto !important;
            background: #ffffff !important;
            color: #000000 !important;
            box-shadow: none !important;
            border: none !important;
            overflow: visible !important;
          }
          .no-print {
            display: none !important;
          }
        }
      `}</style>

      {/* Action Toolbar (hidden during print) */}
      <div className="no-print w-full flex flex-wrap items-center justify-between gap-2 bg-zinc-100 p-3 rounded-t-lg border border-zinc-300 border-b-0">
        <div className="flex items-center space-x-2">
          <label className="flex items-center text-xs font-medium text-zinc-700 cursor-pointer">
            <input
              type="checkbox"
              checked={reprintMode}
              onChange={(e) => setReprintMode(e.target.checked)}
              className="mr-1.5 h-3.5 w-3.5 text-zinc-900 rounded border-zinc-300 focus:ring-zinc-500"
            />
            <span>Reprint Mode</span>
          </label>
        </div>

        <div className="flex items-center space-x-2">
          {receipt.raw_text && (
            <button
              onClick={handleCopyRawText}
              type="button"
              className="px-2.5 py-1 text-xs bg-white text-zinc-700 border border-zinc-300 rounded hover:bg-zinc-50 transition"
              title="Copy ESC/POS monospace text to clipboard"
            >
              {copied ? 'Copied!' : 'Copy Text'}
            </button>
          )}

          <button
            onClick={handlePrint}
            disabled={isPrinting}
            type="button"
            className="px-4 py-1.5 bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold rounded shadow-sm flex items-center gap-1.5 transition"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"
              />
            </svg>
            Print (58mm)
          </button>

          {onClose && (
            <button
              onClick={onClose}
              type="button"
              className="px-2.5 py-1.5 bg-zinc-200 hover:bg-zinc-300 text-zinc-700 text-xs font-medium rounded transition"
            >
              Close
            </button>
          )}
        </div>
      </div>

      {/* ===================================================================
          Physical 58mm Thermal Receipt Visual Paper Layout
          =================================================================== */}
      <div
        id="viyon-thermal-receipt"
        ref={receiptPrintRef}
        className="w-[280px] bg-white text-black font-mono text-xs leading-tight p-4 shadow-xl border border-zinc-200 select-none box-border"
        style={{
          fontFamily: "'Courier New', Courier, monospace",
          letterSpacing: '-0.25px',
        }}
      >
        {/* 1. Header */}
        <div className="text-center pb-1">
          <h1 className="text-base font-extrabold tracking-wider">{store.store_name}</h1>
          {store.tagline && (
            <p className="text-[11px] font-semibold text-zinc-700">{store.tagline}</p>
          )}
          <p className="text-[10px] text-zinc-600 mt-0.5 leading-snug px-1">{store.address}</p>
          <p className="text-[10px] font-bold text-zinc-800">Phone: {store.phone}</p>
          {store.gstin && (
            <p className="text-[10px] text-zinc-700">GSTIN: {store.gstin}</p>
          )}
        </div>

        <div className="border-t-2 border-black my-1.5"></div>

        {/* 2. Reprint Badge */}
        {reprintMode && (
          <div className="my-1.5 py-1 px-2 border border-dashed border-black text-center font-extrabold text-[11px] tracking-widest bg-zinc-50">
            *** DUPLICATE / REPRINT ***
          </div>
        )}

        {/* 3. Cancellation Warning Banner */}
        {is_cancelled && (
          <div className="my-1.5 p-1.5 border-2 border-dashed border-red-600 bg-red-50 text-red-800 text-center text-[10px]">
            <div className="font-extrabold text-[11px] text-red-900 tracking-wider">
              *** BILL CANCELLED ***
            </div>
            {cancellation_details?.cancelled_at && (
              <div>At: {formatDateTime(cancellation_details.cancelled_at)}</div>
            )}
            {cancellation_details?.cancelled_by_user && (
              <div>By: {cancellation_details.cancelled_by_user}</div>
            )}
            {cancellation_details?.cancellation_reason && (
              <div className="font-medium italic mt-0.5">
                Reason: {cancellation_details.cancellation_reason}
              </div>
            )}
          </div>
        )}

        {/* 4. Bill Metadata */}
        <div className="text-[11px] space-y-0.5 py-0.5">
          <div className="flex justify-between">
            <span className="font-bold">Bill No:</span>
            <span className="font-bold">{receipt.bill_number}</span>
          </div>
          <div className="flex justify-between">
            <span>Date:</span>
            <span>{formatDateTime(receipt.bill_date)}</span>
          </div>
          <div className="flex justify-between">
            <span>Cashier:</span>
            <span className="truncate max-w-[150px]">{cashier.full_name}</span>
          </div>
          <div className="flex justify-between">
            <span>Customer:</span>
            <span className="truncate max-w-[150px]">
              {customer?.full_name ? customer.full_name : 'Walk-in Retail'}
            </span>
          </div>
          {customer?.phone_number && (
            <div className="flex justify-between">
              <span>Phone:</span>
              <span>{customer.phone_number}</span>
            </div>
          )}
        </div>

        {/* 5. Product Table */}
        <div className="border-t border-dashed border-black my-1.5"></div>
        <div className="flex justify-between font-bold text-[10px] pb-1 border-b border-black">
          <span>ITEM DESCRIPTION</span>
          <span>TOTAL</span>
        </div>

        <div className="py-1 space-y-1.5 text-[11px]">
          {items.map((it, idx) => {
            const hasVariants = it.sku || it.size || it.color;
            const hasDiscount = parseFloat(String(it.discount_amount || 0)) > 0;
            return (
              <div key={it.id || idx} className="border-b border-dotted border-zinc-300 pb-1">
                {/* Product Name (wraps onto multiple lines) */}
                <div className="font-bold text-zinc-900 leading-tight break-words">
                  {it.product_name}
                </div>

                {/* SKU / Size / Color metadata */}
                {hasVariants && (
                  <div className="text-[10px] text-zinc-600 flex flex-wrap gap-x-1.5">
                    {it.sku && <span>SKU: {it.sku}</span>}
                    {it.size && <span>Size: {it.size}</span>}
                    {it.color && <span>Col: {it.color}</span>}
                  </div>
                )}

                {/* Calculation row: Qty x Price -> Total */}
                <div className="flex justify-between items-baseline text-[10px] text-zinc-800 mt-0.5">
                  <span>
                    {it.quantity} &times; {formatCurrency(it.unit_price)}
                  </span>
                  <span className="font-bold text-[11px] text-zinc-900">
                    {formatCurrency(it.line_total)}
                  </span>
                </div>

                {/* Item level discount */}
                {hasDiscount && (
                  <div className="text-[10px] text-red-600">
                    Item Disc: -{formatCurrency(it.discount_amount)}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* 6. Price Summary */}
        <div className="border-t border-dashed border-black my-1"></div>
        <div className="space-y-0.5 text-[11px]">
          <div className="flex justify-between">
            <span>Subtotal:</span>
            <span>{formatCurrency(receipt.subtotal)}</span>
          </div>

          {parseFloat(String(receipt.item_discount_total || 0)) > 0 && (
            <div className="flex justify-between text-red-600">
              <span>Item Discounts:</span>
              <span>-{formatCurrency(receipt.item_discount_total)}</span>
            </div>
          )}

          {parseFloat(String(receipt.bill_discount_amount || 0)) > 0 && (
            <div className="flex justify-between text-red-600">
              <span>Bill Discount:</span>
              <span>-{formatCurrency(receipt.bill_discount_amount)}</span>
            </div>
          )}

          {parseFloat(String(receipt.tax_amount || 0)) > 0 && (
            <div className="flex justify-between">
              <span>Tax:</span>
              <span>{formatCurrency(receipt.tax_amount)}</span>
            </div>
          )}

          <div className="border-t border-black my-1"></div>
          <div className="flex justify-between font-extrabold text-[13px] py-0.5">
            <span>GRAND TOTAL:</span>
            <span>{formatCurrency(receipt.grand_total)}</span>
          </div>
          <div className="border-b-2 border-black my-1"></div>
        </div>

        {/* 7. Payment Information */}
        <div className="space-y-0.5 text-[11px] py-1">
          <div className="flex justify-between font-bold">
            <span>Payment Method:</span>
            <span>{receipt.payment_method}</span>
          </div>

          {parseFloat(String(payment_breakdown.confirmed_cash || 0)) > 0 && (
            <div className="flex justify-between pl-2 text-[10px] text-zinc-700">
              <span>Cash Confirmed:</span>
              <span>{formatCurrency(payment_breakdown.confirmed_cash)}</span>
            </div>
          )}

          {parseFloat(String(payment_breakdown.confirmed_upi || 0)) > 0 && (
            <div className="flex justify-between pl-2 text-[10px] text-zinc-700">
              <span>UPI Confirmed:</span>
              <span>{formatCurrency(payment_breakdown.confirmed_upi)}</span>
            </div>
          )}

          <div className="border-t border-dotted border-zinc-400 my-1"></div>
          <div className="flex justify-between font-bold">
            <span>Amount Paid:</span>
            <span>{formatCurrency(receipt.amount_paid)}</span>
          </div>
          <div className="flex justify-between font-bold">
            <span>Balance Due:</span>
            <span>{formatCurrency(receipt.balance)}</span>
          </div>

          {/* Refund Review amount on cancelled bills */}
          {is_cancelled &&
            cancellation_details?.refund_review_amount &&
            parseFloat(String(cancellation_details.refund_review_amount)) > 0 && (
              <div className="flex justify-between font-bold text-red-700 pt-1">
                <span>Refund Review:</span>
                <span>{formatCurrency(cancellation_details.refund_review_amount)}</span>
              </div>
            )}
        </div>

        {/* 8. Pending UPI Warning Box */}
        {payment_breakdown.has_pending_upi && (
          <div className="my-2 p-1.5 border border-dashed border-amber-500 bg-amber-50 text-amber-900 text-center text-[10px]">
            <div className="font-bold text-[11px] tracking-wide">*** UPI PAYMENT PENDING ***</div>
            <div className="font-semibold">
              Amount: {formatCurrency(payment_breakdown.pending_upi)}
            </div>
            <div className="text-[9px] text-amber-700 mt-0.5">
              (Awaiting Staff Verification - Not Counted in Paid)
            </div>
          </div>
        )}

        {/* 9. Footer */}
        <div className="border-t-2 border-black my-2"></div>
        <div className="text-center text-[10px] text-zinc-700 space-y-0.5">
          {store.receipt_footer && (
            <p className="font-medium text-zinc-800">{store.receipt_footer}</p>
          )}
          <p className="font-bold text-[11px] tracking-wide text-black mt-1">Visit again!</p>
        </div>
        <div className="border-b-2 border-black my-2"></div>
      </div>
    </div>
  );
};

export default ReceiptPreview;
