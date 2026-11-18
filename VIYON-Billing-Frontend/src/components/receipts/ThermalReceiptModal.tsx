import React, { useState, useEffect } from 'react';
import { X, Printer, Check, AlertCircle, Copy, FileText, Eye } from 'lucide-react';
import { ReceiptPreviewOut, ReceiptOut } from '../../types';
import { billingService } from '../../services/billingService';
import { getErrorMessage } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

interface ThermalReceiptModalProps {
  billId: string | null;
  onClose: () => void;
  isReprint?: boolean;
}

export const ThermalReceiptModal: React.FC<ThermalReceiptModalProps> = ({
  billId,
  onClose,
  isReprint = false,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [receiptData, setReceiptData] = useState<ReceiptPreviewOut | ReceiptOut | null>(null);
  const [activeTab, setActiveTab] = useState<'visual' | 'monospace'>('visual');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!billId) return;
    setLoading(true);
    setError(null);
    billingService
      .getReceipt(billId, isReprint)
      .then((data) => {
        setReceiptData(data);
      })
      .catch((err) => {
        setError(getErrorMessage(err));
      })
      .finally(() => setLoading(false));
  }, [billId, isReprint]);

  // Robustly extract data whether response is ReceiptPreviewOut ({ receipt_data }) or ReceiptOut
  const data: ReceiptOut | undefined =
    receiptData && 'receipt_data' in receiptData && (receiptData as any).receipt_data
      ? (receiptData as any).receipt_data
      : (receiptData as unknown as ReceiptOut);

  const formattedMonospace: string =
    (receiptData as any)?.formatted_text ||
    (receiptData as any)?.raw_text ||
    data?.raw_text ||
    '';

  const handlePrint = async () => {
    if (!billId) return;
    try {
      await billingService.recordPrintAudit(billId, isReprint);
    } catch {
      // Audit log failed gracefully
    }
    window.print();
  };

  const handleCopyMonospace = () => {
    if (!formattedMonospace) return;
    navigator.clipboard.writeText(formattedMonospace);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!billId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm print:p-0 print:bg-white">
      {/* Modal Dialog */}
      <div className="relative flex max-h-[92vh] w-full max-w-lg flex-col rounded-2xl bg-white shadow-2xl print:max-h-none print:w-full print:shadow-none print:border-none">
        {/* Header (Hidden in Print) */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 print:hidden">
          <div className="flex items-center gap-2">
            <Printer className="h-5 w-5 text-amber-500" />
            <h3 className="text-base font-bold text-zinc-900">
              {isReprint ? 'Reprint 58mm Thermal Receipt' : '58mm Thermal Receipt Preview'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab Switcher & Hardware Notice (Hidden in Print) */}
        <div className="border-b border-zinc-100 bg-zinc-50 px-6 py-2.5 print:hidden">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1 rounded-lg bg-zinc-200/60 p-1 text-xs">
              <button
                onClick={() => setActiveTab('visual')}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition-all ${
                  activeTab === 'visual'
                    ? 'bg-white text-zinc-900 shadow-sm'
                    : 'text-zinc-600 hover:text-zinc-900'
                }`}
              >
                <Eye className="h-3.5 w-3.5" />
                <span>Visual Receipt</span>
              </button>
              <button
                onClick={() => setActiveTab('monospace')}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition-all ${
                  activeTab === 'monospace'
                    ? 'bg-white text-zinc-900 shadow-sm'
                    : 'text-zinc-600 hover:text-zinc-900'
                }`}
              >
                <FileText className="h-3.5 w-3.5" />
                <span>32-Col Raw Monospace</span>
              </button>
            </div>

            {activeTab === 'monospace' && (
              <button
                onClick={handleCopyMonospace}
                className="flex items-center gap-1 text-xs font-medium text-zinc-600 hover:text-zinc-900"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                <span>{copied ? 'Copied' : 'Copy Text'}</span>
              </button>
            )}
          </div>

          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-amber-700 bg-amber-50 rounded px-2.5 py-1 border border-amber-200/70">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span>
              <strong>Hardware status:</strong> PHYSICAL PRINTER HARDWARE TEST PENDING. Browser print ready.
            </span>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-zinc-100/60 print:p-0 print:bg-white">
          {loading ? (
            <div className="flex h-64 flex-col items-center justify-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
              <p className="text-xs text-zinc-500">Generating receipt snapshot...</p>
            </div>
          ) : error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-center text-xs text-rose-700">
              {error}
            </div>
          ) : (
            <>
              {/* Monospace Tab (Screen view only) */}
              {activeTab === 'monospace' && (
                <div className="rounded-xl border border-zinc-300 bg-white p-4 shadow-inner print:hidden">
                  <pre className="font-mono text-[13px] font-bold leading-tight text-black whitespace-pre overflow-x-auto select-all">
                    {formattedMonospace}
                  </pre>
                </div>
              )}

              {/* Visual 58mm Thermal Receipt (Screen view when activeTab=visual, ALWAYS active for print) */}
              <div
                id="printable-thermal-receipt"
                className={`mx-auto w-[310px] border border-dashed border-black bg-white p-4 font-sans text-[11px] leading-tight text-black shadow-md select-none print:w-full print:border-none print:shadow-none print:p-0 ${
                  activeTab === 'monospace' ? 'hidden print:block' : 'block'
                }`}
              >
                {/* Store Header */}
                <div className="text-center border-b border-dashed border-black pb-2">
                  <h2 className="text-xl font-black tracking-widest text-black uppercase">
                    {data?.store.store_name || 'VIYON'}
                  </h2>
                  <p className="text-[11px] font-bold text-black uppercase tracking-wider">
                    {data?.store.tagline || "MEN'S COLLECTIONS"}
                  </p>
                  <p className="mt-1 text-[11px] font-semibold text-black leading-snug">
                    {data?.store.address}
                  </p>
                  <p className="text-[11px] font-bold text-black">
                    Phone: {data?.store.phone}
                  </p>
                  {data?.store.gstin && (
                    <p className="text-[11px] font-bold text-black">GSTIN: {data.store.gstin}</p>
                  )}
                  {isReprint && (
                    <div className="mt-1.5 inline-block border-2 border-black bg-white px-2.5 py-0.5 text-[11px] font-black tracking-wider text-black uppercase">
                      *** DUPLICATE REPRINT ***
                    </div>
                  )}
                </div>

                {/* Bill & Date Info */}
                <div className="border-b border-dashed border-black py-2 text-[11px] space-y-0.5 text-black">
                  <div className="flex justify-between">
                    <span className="font-bold">Bill No:</span>
                    <span className="font-black">{data?.bill_number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-bold">Date:</span>
                    <span className="font-bold">{formatDateTime(data?.bill_date)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-bold">Cashier:</span>
                    <span className="font-bold truncate max-w-[160px]">{data?.cashier.full_name}</span>
                  </div>
                  {data?.customer?.full_name && (
                    <div className="flex justify-between">
                      <span className="font-bold">Customer:</span>
                      <span className="font-bold">{data.customer.full_name}</span>
                    </div>
                  )}
                </div>

                {/* Items Line Breakdown */}
                <div className="border-b border-dashed border-black py-2 text-black">
                  <div className="flex justify-between font-black text-[11px] pb-1 border-b-2 border-black uppercase text-black">
                    <span className="w-[50%] text-left">Item</span>
                    <span className="w-[25%] text-center">Qty×Price</span>
                    <span className="w-[25%] text-right">Total</span>
                  </div>
                  <div className="pt-1.5 space-y-1.5">
                    {data?.items.map((item, idx) => (
                      <div key={idx} className="space-y-0.5">
                        <div className="font-bold text-[12px] leading-snug text-black break-words whitespace-normal">
                          {item.product_name}
                        </div>
                        <div className="flex justify-between text-[11px] font-semibold text-black">
                          <span className="w-[50%] text-left break-words">
                            {item.size ? `Size: ${item.size}` : ''}
                            {item.sku ? ` (${item.sku})` : ''}
                          </span>
                          <span className="w-[25%] text-center font-bold">
                            {item.quantity} × {formatCurrency(item.unit_price)}
                          </span>
                          <span className="w-[25%] text-right font-black text-black">
                            {formatCurrency(item.line_total)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Summary & Totals */}
                <div className="border-b border-dashed border-black py-2 space-y-1 text-[11px] text-black">
                  <div className="flex justify-between font-bold">
                    <span>Subtotal:</span>
                    <span className="font-bold">{formatCurrency(data?.subtotal)}</span>
                  </div>
                  {Number(data?.discount_amount) > 0 && (
                    <div className="flex justify-between font-bold text-black">
                      <span>Bill Discount:</span>
                      <span className="font-bold">-{formatCurrency(data?.discount_amount)}</span>
                    </div>
                  )}
                  {Number(data?.tax_amount) > 0 && (
                    <div className="flex justify-between font-bold text-black">
                      <span>GST:</span>
                      <span className="font-bold">{formatCurrency(data?.tax_amount)}</span>
                    </div>
                  )}
                  {/* GRAND TOTAL: Prominent, heavily bolded with double-line styling */}
                  <div className="my-1.5 flex justify-between border-y-2 border-black py-1.5 text-[13px] font-black tracking-wide text-black">
                    <span className="font-black">GRAND TOTAL:</span>
                    <span className="text-base font-black">{formatCurrency(data?.grand_total)}</span>
                  </div>
                </div>

                {/* Payment Info */}
                <div className="border-b border-dashed border-black py-2 text-[11px] space-y-1 text-black">
                  <div className="flex justify-between font-bold">
                    <span>Amount Paid:</span>
                    <span className="font-black">{formatCurrency(data?.amount_paid)}</span>
                  </div>
                  {Number(data?.balance) > 0 && (
                    <div className="flex justify-between font-black text-black">
                      <span>Balance Due:</span>
                      <span className="font-black">{formatCurrency(data?.balance)}</span>
                    </div>
                  )}
                  <div className="flex justify-between font-bold text-black">
                    <span>Payment Method:</span>
                    <span className="font-bold uppercase">{data?.payment_method}</span>
                  </div>
                  <div className="flex justify-between font-bold text-black">
                    <span>PAYMENT STATUS:</span>
                    <span className="font-black uppercase">{data?.payment_status || 'PAID'}</span>
                  </div>
                  {data?.payment_breakdown?.payments && data.payment_breakdown.payments.length > 1 && (
                    <div className="mt-1 border-t border-dashed border-black pt-1 space-y-0.5 text-[10px] text-black">
                      <span className="font-bold">Split Payment Breakdown:</span>
                      {data.payment_breakdown.payments.map((p, idx) => (
                        <div key={idx} className="flex justify-between font-semibold text-black">
                          <span>• {p.payment_method} Paid:</span>
                          <span className="font-bold">{formatCurrency(p.amount)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Footer Thank You & Terms */}
                <div className="pt-2 text-center text-[10px] font-bold text-black space-y-0.5">
                  <p className="text-[11px] font-black uppercase">
                    {data?.store.receipt_footer || 'Thank you for shopping at VIYON!'}
                  </p>
                  <p className="font-semibold">Goods once sold can be exchanged within 7 days with original receipt.</p>
                  <p className="font-black pt-0.5 tracking-wider">*** HAVE A GREAT DAY ***</p>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Modal Actions Footer (Hidden in Print) */}
        <div className="flex items-center justify-between border-t border-zinc-200 bg-white px-6 py-4 print:hidden">
          <button
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
          >
            Close
          </button>
          <button
            onClick={handlePrint}
            disabled={loading || !!error}
            className="flex items-center gap-2 rounded-lg bg-amber-500 px-5 py-2 text-xs font-semibold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95 disabled:opacity-50"
          >
            <Printer className="h-4 w-4" />
            <span>Print Receipt</span>
          </button>
        </div>
      </div>
    </div>
  );
};
