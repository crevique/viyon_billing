import React, { useState, useEffect } from 'react';
import { CreditCard, Plus, Search, Check, RefreshCw, X } from 'lucide-react';
import { SupplierPayment, Supplier } from '../../types';
import { purchaseService, SupplierPaymentPayload } from '../../services/purchaseService';
import { supplierService } from '../../services/supplierService';
import { useAuthStore } from '../../stores/useAuthStore';
import { formatCurrency, formatDateTime, getStatusBadgeClass } from '../../utils/formatters';

export const SupplierPaymentsPage: React.FC = () => {
  const { role } = useAuthStore();
  const isOwner = role === 'OWNER' || role === 'ADMIN';

  const [payments, setPayments] = useState<SupplierPayment[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedSupplierId, setSelectedSupplierId] = useState('');
  const [amount, setAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<'CASH' | 'UPI' | 'BANK_TRANSFER' | 'CHEQUE'>('BANK_TRANSFER');
  const [transactionRef, setTransactionRef] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    loadPayments();
    loadSuppliers();
  }, []);

  const loadPayments = async () => {
    setLoading(true);
    try {
      const res = await purchaseService.getPayments({ limit: 100 });
      setPayments(res.items || []);
    } catch (err) {
      console.error('Failed to load supplier payments', err);
    } finally {
      setLoading(false);
    }
  };

  const loadSuppliers = async () => {
    try {
      const res = await supplierService.getSuppliers({ limit: 100 });
      setSuppliers(res.items || []);
    } catch (err) {
      console.error('Failed to load suppliers', err);
    }
  };

  const handleOpenModal = () => {
    setSelectedSupplierId(suppliers[0]?.id || '');
    setAmount('');
    setPaymentMethod('BANK_TRANSFER');
    setTransactionRef('');
    setNotes('');
    setIsModalOpen(true);
  };

  const handlePaymentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(amount);
    if (!selectedSupplierId || !val || val <= 0) {
      alert('Please select a supplier and enter a valid positive payment amount.');
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: SupplierPaymentPayload = {
        supplier_id: selectedSupplierId,
        payment_method: paymentMethod,
        amount: val,
        transaction_reference: transactionRef.trim() || undefined,
        notes: notes.trim() || undefined,
      };

      await purchaseService.recordPayment(payload);
      alert('Supplier payment recorded successfully.');
      setIsModalOpen(false);
      loadPayments();
    } catch (err: any) {
      alert(`Payment recording failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmPayment = async (paymentId: string) => {
    if (!window.confirm('Confirm this supplier payment?')) return;
    try {
      await purchaseService.confirmPayment(paymentId);
      alert('Supplier payment confirmed.');
      loadPayments();
    } catch (err: any) {
      alert(`Confirmation failed: ${err.message || 'Unknown error'}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Supplier Settlements & Payments
          </h2>
          <p className="text-xs text-zinc-500">
            Record bank transfers, cheques, and cash disbursements against vendor procurement invoices.
          </p>
        </div>

        {isOwner && (
          <button
            onClick={handleOpenModal}
            className="flex items-center gap-1.5 self-start sm:self-auto rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95"
          >
            <Plus className="h-4 w-4" />
            <span>Record Supplier Payment</span>
          </button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading payment records...</p>
          </div>
        ) : payments.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            No supplier payments recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">Payment #</th>
                  <th className="py-3 px-4">Supplier</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Method</th>
                  <th className="py-3 px-4">Reference / UTR</th>
                  <th className="py-3 px-4 text-right">Amount Paid</th>
                  <th className="py-3 px-4">Status</th>
                  {isOwner && <th className="py-3 px-4 text-center">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {payments.map((p) => (
                  <tr key={p.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-zinc-900">{p.payment_number}</td>
                    <td className="py-3 px-4 font-semibold text-zinc-800">{p.supplier_name || '—'}</td>
                    <td className="py-3 px-4 text-zinc-500">{formatDateTime(p.payment_date)}</td>
                    <td className="py-3 px-4 font-medium text-zinc-700">{p.payment_method}</td>
                    <td className="py-3 px-4 font-mono text-zinc-500">{p.transaction_reference || '—'}</td>
                    <td className="py-3 px-4 text-right font-black text-sm text-emerald-600">
                      {formatCurrency(p.amount)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getStatusBadgeClass(p.status)}`}>
                        {p.status}
                      </span>
                    </td>
                    {isOwner && (
                      <td className="py-3 px-4 text-center">
                        {p.status === 'PENDING' && (
                          <button
                            onClick={() => handleConfirmPayment(p.id)}
                            className="rounded bg-emerald-600 text-white font-bold px-2.5 py-1 text-[11px] hover:bg-emerald-500"
                          >
                            Confirm
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Record Payment Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="text-base font-bold text-zinc-900">Record Vendor Disbursement</h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handlePaymentSubmit} className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Select Supplier *
                </label>
                <select
                  required
                  value={selectedSupplierId}
                  onChange={(e) => setSelectedSupplierId(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
                >
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.company_name} (Balance: {formatCurrency(s.outstanding_balance)})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Payment Method *
                </label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value as any)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
                >
                  <option value="BANK_TRANSFER">Bank Transfer (NEFT/RTGS/IMPS)</option>
                  <option value="UPI">UPI</option>
                  <option value="CHEQUE">Cheque</option>
                  <option value="CASH">Cash</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Payment Amount (₹) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  placeholder="e.g. 25000.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs font-bold text-zinc-900 focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Bank Reference / UTR / Cheque No.
                </label>
                <input
                  type="text"
                  placeholder="e.g. UTR-901428"
                  value={transactionRef}
                  onChange={(e) => setTransactionRef(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Notes
                </label>
                <textarea
                  rows={2}
                  placeholder="Settlement notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  disabled={isSubmitting}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 rounded-xl bg-amber-500 py-2 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400 disabled:opacity-50"
                >
                  {isSubmitting ? 'Recording...' : 'Record Payment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
