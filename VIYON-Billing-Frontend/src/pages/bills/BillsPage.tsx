import React, { useState, useEffect } from 'react';
import {
  Search,
  Receipt,
  Filter,
  Eye,
  Printer,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Check,
  ChevronRight,
  X,
  CreditCard,
} from 'lucide-react';
import { Bill, Payment } from '../../types';
import { billingService } from '../../services/billingService';
import { useAuthStore } from '../../stores/useAuthStore';
import { formatCurrency, formatDateTime, getStatusBadgeClass } from '../../utils/formatters';
import { ThermalReceiptModal } from '../../components/receipts/ThermalReceiptModal';

export const BillsPage: React.FC = () => {
  const { role } = useAuthStore();
  const isOwner = role === 'OWNER' || role === 'ADMIN';

  // Filters & Pagination
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [search, setSearch] = useState<string>('');
  const [paymentStatus, setPaymentStatus] = useState<string>('');
  const [billStatus, setBillStatus] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const pageSize = 20;

  // Selected Bill Details Modal
  const [selectedBill, setSelectedBill] = useState<Bill | null>(null);
  const [billPayments, setBillPayments] = useState<Payment[]>([]);
  const [loadingPayments, setLoadingPayments] = useState<boolean>(false);

  // Cancellation Modal (Owner Only)
  const [cancellingBill, setCancellingBill] = useState<Bill | null>(null);
  const [cancellationReason, setCancellationReason] = useState<string>('');
  const [isCancelling, setIsCancelling] = useState<boolean>(false);

  // Receipt Modal
  const [receiptBillId, setReceiptBillId] = useState<string | null>(null);

  // Confirmation action state
  const [isConfirmingPayment, setIsConfirmingPayment] = useState<string | null>(null);

  useEffect(() => {
    loadBills();
  }, [page, paymentStatus, billStatus]);

  const loadBills = async () => {
    setLoading(true);
    try {
      const res = await billingService.getBills({
        page,
        page_size: pageSize,
        search: search.trim() || undefined,
        payment_status: paymentStatus || undefined,
        status: billStatus || undefined,
      });
      setBills(res.items || []);
      setTotalCount(res.total || 0);
    } catch (err) {
      console.error('Failed to load bills', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadBills();
  };

  const handleViewBill = async (bill: Bill) => {
    setSelectedBill(bill);
    setLoadingPayments(true);
    try {
      const payments = await billingService.getBillPayments(bill.id);
      setBillPayments(payments || []);
    } catch (err) {
      console.error('Failed to fetch bill payments', err);
    } finally {
      setLoadingPayments(false);
    }
  };

  const handleConfirmUPI = async (paymentId: string) => {
    if (!window.confirm('Verify that funds have officially been received in the store bank/UPI app. Confirm this payment?')) {
      return;
    }

    setIsConfirmingPayment(paymentId);
    try {
      await billingService.confirmPayment(paymentId, 'Confirmed after merchant app verification.');
      // Refresh selected bill and bill list
      if (selectedBill) {
        const updatedBill = await billingService.getBillById(selectedBill.id);
        const payments = await billingService.getBillPayments(selectedBill.id);
        setSelectedBill(updatedBill);
        setBillPayments(payments);
      }
      loadBills();
    } catch (err: any) {
      alert(`Payment confirmation failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsConfirmingPayment(null);
    }
  };

  const handleCancelBillSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancellingBill) return;
    if (cancellationReason.trim().length < 3) {
      alert('A cancellation reason of at least 3 characters is mandatory.');
      return;
    }

    setIsCancelling(true);
    try {
      await billingService.cancelBill(cancellingBill.id, cancellationReason.trim());
      alert(`Bill ${cancellingBill.bill_number} has been cancelled. Inventory was automatically restored.`);
      setCancellingBill(null);
      setCancellationReason('');
      if (selectedBill?.id === cancellingBill.id) {
        setSelectedBill(null);
      }
      loadBills();
    } catch (err: any) {
      alert(`Cancellation failed: ${err.message || 'Error cancelling bill'}`);
    } finally {
      setIsCancelling(false);
    }
  };

  const confirmedPayments = billPayments.filter((p) => p.payment_status === 'CONFIRMED');
  const pendingPayments = billPayments.filter((p) => p.payment_status === 'PENDING');

  return (
    <div className="space-y-5">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Bills & Sales Transactions
          </h2>
          <p className="text-xs text-zinc-500">
            Search invoices, verify pending UPI payments, reprint thermal receipts, and audit transactions.
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
        <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              placeholder="Search by Bill Number (e.g. BIL-20261113-0001)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-zinc-200 bg-zinc-50 pl-9 pr-4 py-2 text-xs focus:border-amber-500 focus:bg-white focus:outline-none"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={paymentStatus}
              onChange={(e) => {
                setPaymentStatus(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-700 focus:border-amber-500 focus:outline-none"
            >
              <option value="">Payment: All</option>
              <option value="PAID">PAID</option>
              <option value="PENDING">PENDING</option>
              <option value="PARTIAL">PARTIAL</option>
              <option value="FAILED">FAILED</option>
              <option value="REJECTED">REJECTED</option>
            </select>

            <select
              value={billStatus}
              onChange={(e) => {
                setBillStatus(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-700 focus:border-amber-500 focus:outline-none"
            >
              <option value="">Status: All</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="CANCELLED">CANCELLED</option>
            </select>

            <button
              type="submit"
              className="rounded-xl bg-zinc-900 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-zinc-800"
            >
              Search
            </button>
          </div>
        </form>
      </div>

      {/* Bills Data Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading invoices...</p>
          </div>
        ) : bills.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center text-center p-6">
            <Receipt className="h-10 w-10 text-zinc-300 mb-2" />
            <p className="text-sm font-semibold text-zinc-700">No bills found</p>
            <p className="text-xs text-zinc-400">Try modifying your search or filter parameters</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">Bill Number</th>
                  <th className="py-3 px-4">Date & Time</th>
                  <th className="py-3 px-4">Cashier</th>
                  <th className="py-3 px-4 text-right">Items</th>
                  <th className="py-3 px-4 text-right">Total Amount</th>
                  <th className="py-3 px-4 text-right">Amount Paid</th>
                  <th className="py-3 px-4 text-right">Balance</th>
                  <th className="py-3 px-4">Payment</th>
                  <th className="py-3 px-4">Bill Status</th>
                  <th className="py-3 px-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {bills.map((bill) => (
                  <tr key={bill.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-zinc-900">{bill.bill_number}</td>
                    <td className="py-3 px-4 text-zinc-500">{formatDateTime(bill.bill_date)}</td>
                    <td className="py-3 px-4 text-zinc-700">{bill.staff_name || 'Staff'}</td>
                    <td className="py-3 px-4 text-right font-medium">{bill.items?.length || 0}</td>
                    <td className="py-3 px-4 text-right font-bold text-zinc-900">
                      {formatCurrency(bill.total_amount)}
                    </td>
                    <td className="py-3 px-4 text-right text-emerald-600 font-medium">
                      {formatCurrency(bill.amount_paid)}
                    </td>
                    <td className="py-3 px-4 text-right text-amber-600 font-medium">
                      {formatCurrency(bill.balance_amount)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getStatusBadgeClass(bill.payment_status)}`}>
                        {bill.payment_status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getStatusBadgeClass(bill.bill_status)}`}>
                        {bill.bill_status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => handleViewBill(bill)}
                          className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
                          title="View Bill Details & Payments"
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => setReceiptBillId(bill.id)}
                          className="rounded-lg p-1.5 text-amber-600 hover:bg-amber-50"
                          title="Reprint 58mm Receipt"
                        >
                          <Printer className="h-4 w-4" />
                        </button>
                        {isOwner && bill.bill_status !== 'CANCELLED' && (
                          <button
                            onClick={() => {
                              setCancellingBill(bill);
                              setCancellationReason('');
                            }}
                            className="rounded-lg p-1.5 text-rose-500 hover:bg-rose-50 hover:text-rose-700"
                            title="Cancel Bill (Owner Only)"
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Bill Details Modal Drawer */}
      {selectedBill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-3 sm:p-4 backdrop-blur-sm">
          <div className="relative flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-zinc-200 px-4 sm:px-6 py-3 sm:py-4">
              <div>
                <h3 className="text-base font-bold text-zinc-900">
                  Bill {selectedBill.bill_number}
                </h3>
                <p className="text-xs text-zinc-500">
                  Generated {formatDateTime(selectedBill.bill_date)} by {selectedBill.staff_name || 'Staff'}
                </p>
              </div>
              <button
                onClick={() => setSelectedBill(null)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
              {/* Financial Snapshot */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-center">
                <div>
                  <span className="text-[10px] text-zinc-500 font-semibold uppercase">Subtotal</span>
                  <p className="text-sm font-bold text-zinc-800">
                    {formatCurrency(selectedBill.subtotal)}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-500 font-semibold uppercase">Bill Discount</span>
                  <p className="text-sm font-bold text-emerald-600">
                    {Number(selectedBill.discount_amount) > 0 ? `-${formatCurrency(selectedBill.discount_amount)}` : '₹0.00'}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-500 font-semibold uppercase">Grand Total</span>
                  <p className="text-sm font-black text-zinc-900">
                    {formatCurrency(selectedBill.total_amount)}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-500 font-semibold uppercase">Confirmed Paid</span>
                  <p className="text-sm font-black text-emerald-600">
                    {formatCurrency(selectedBill.amount_paid)}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-500 font-semibold uppercase">Balance Due</span>
                  <p className="text-sm font-black text-amber-600">
                    {formatCurrency(selectedBill.balance_amount)}
                  </p>
                </div>
              </div>

              {/* Items Table */}
              <div>
                <h4 className="text-xs font-bold text-zinc-900 mb-2">Purchased Items</h4>
                <div className="rounded-xl border border-zinc-200 overflow-x-auto">
                  <table className="w-full text-left text-xs min-w-[460px]">
                    <thead className="bg-zinc-50 text-zinc-600 border-b border-zinc-200 font-semibold">
                      <tr>
                        <th className="py-2 px-3">Item</th>
                        <th className="py-2 px-3">SKU</th>
                        <th className="py-2 px-3 text-right">Qty</th>
                        <th className="py-2 px-3 text-right">Unit Price</th>
                        <th className="py-2 px-3 text-right">Line Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {selectedBill.items?.map((item, idx) => (
                        <tr key={idx}>
                          <td className="py-2 px-3 font-semibold text-zinc-800">
                            {item.product_name_snapshot}
                            {item.size_snapshot && ` (Size: ${item.size_snapshot})`}
                          </td>
                          <td className="py-2 px-3 font-mono text-zinc-400">{item.sku_snapshot}</td>
                          <td className="py-2 px-3 text-right">{item.quantity}</td>
                          <td className="py-2 px-3 text-right">{formatCurrency(item.unit_price)}</td>
                          <td className="py-2 px-3 text-right font-bold text-zinc-900">
                            {formatCurrency(item.line_total)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Payments Breakdown: Confirmed vs Pending */}
              <div>
                <h4 className="text-xs font-bold text-zinc-900 mb-2">Counter Payments Breakdown</h4>
                {loadingPayments ? (
                  <p className="text-xs text-zinc-400">Loading payment records...</p>
                ) : (
                  <div className="space-y-3">
                    {/* Confirmed Payments */}
                    <div>
                      <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider">
                        Confirmed Payments ({confirmedPayments.length})
                      </span>
                      {confirmedPayments.length === 0 ? (
                        <p className="text-xs text-zinc-400 italic">No confirmed payments yet.</p>
                      ) : (
                        <div className="mt-1 space-y-1.5">
                          {confirmedPayments.map((p) => (
                            <div
                              key={p.id}
                              className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50/50 p-2.5 text-xs"
                            >
                              <div>
                                <span className="font-bold text-emerald-900">
                                  {p.payment_method} • {formatCurrency(p.amount)}
                                </span>
                                <p className="text-[11px] text-zinc-500">
                                  Received {formatDateTime(p.received_at)}
                                  {p.transaction_reference && ` • Ref: ${p.transaction_reference}`}
                                </p>
                              </div>
                              <span className="rounded bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 text-[10px]">
                                CONFIRMED
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Pending UPI Payments (Requires Verification) */}
                    <div>
                      <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider">
                        Pending UPI Payments ({pendingPayments.length})
                      </span>
                      {pendingPayments.length === 0 ? (
                        <p className="text-xs text-zinc-400 italic">No pending UPI payments.</p>
                      ) : (
                        <div className="mt-1 space-y-1.5">
                          {pendingPayments.map((p) => (
                            <div
                              key={p.id}
                              className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50/70 p-2.5 text-xs"
                            >
                              <div>
                                <span className="font-bold text-amber-950">
                                  UPI • {formatCurrency(p.amount)}
                                </span>
                                <p className="text-[11px] text-zinc-600">
                                  Ref: {p.transaction_reference || 'No UTR specified'} • {formatDateTime(p.received_at)}
                                </p>
                              </div>
                              <button
                                onClick={() => handleConfirmUPI(p.id)}
                                disabled={isConfirmingPayment === p.id}
                                className="flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1 text-xs font-bold text-white shadow-sm hover:bg-emerald-500 disabled:opacity-50"
                              >
                                <Check className="h-3.5 w-3.5" />
                                <span>{isConfirmingPayment === p.id ? 'Confirming...' : 'Confirm Received'}</span>
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-between border-t border-zinc-200 bg-zinc-50 px-6 py-3">
              <button
                onClick={() => setReceiptBillId(selectedBill.id)}
                className="flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3.5 py-1.5 text-xs font-bold text-zinc-700 hover:bg-zinc-100"
              >
                <Printer className="h-4 w-4 text-amber-500" />
                <span>Print Thermal Receipt</span>
              </button>

              <button
                onClick={() => setSelectedBill(null)}
                className="rounded-lg bg-zinc-900 px-4 py-1.5 text-xs font-bold text-white hover:bg-zinc-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bill Cancellation Modal (Owner Only) */}
      {cancellingBill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-600 mb-3">
              <AlertTriangle className="h-6 w-6" />
              <h3 className="text-base font-bold text-zinc-900">Cancel Sales Bill</h3>
            </div>
            <p className="text-xs text-zinc-600 mb-4">
              You are about to cancel bill <strong>{cancellingBill.bill_number}</strong> (Total: {formatCurrency(cancellingBill.total_amount)}).
              This will restore all inventory line items back to sellable stock.
            </p>

            <form onSubmit={handleCancelBillSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-zinc-700 mb-1">
                  Mandatory Cancellation Reason:
                </label>
                <textarea
                  rows={3}
                  placeholder="e.g. Customer returned goods at counter, wrong size billed..."
                  value={cancellationReason}
                  onChange={(e) => setCancellationReason(e.target.value)}
                  required
                  minLength={3}
                  className="w-full rounded-xl border border-zinc-300 p-2.5 text-xs text-zinc-900 focus:border-rose-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setCancellingBill(null)}
                  disabled={isCancelling}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Abort
                </button>
                <button
                  type="submit"
                  disabled={isCancelling || cancellationReason.trim().length < 3}
                  className="flex-1 rounded-xl bg-rose-600 py-2 text-xs font-bold text-white shadow-md hover:bg-rose-500 disabled:opacity-50"
                >
                  {isCancelling ? 'Processing...' : 'Confirm Cancellation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Thermal Receipt Preview Modal */}
      {receiptBillId && (
        <ThermalReceiptModal
          billId={receiptBillId}
          onClose={() => setReceiptBillId(null)}
          isReprint={true}
        />
      )}
    </div>
  );
};
