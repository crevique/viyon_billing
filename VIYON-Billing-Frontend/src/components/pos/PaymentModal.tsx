import React, { useState } from 'react';
import { X, DollarSign, Smartphone, Split, AlertCircle, CheckCircle2 } from 'lucide-react';
import { formatCurrency } from '../../utils/formatters';
import { getErrorMessage } from '../../services/api';

export type PaymentType = 'CASH' | 'UPI' | 'SPLIT';

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  grandTotal: number;
  isProcessing: boolean;
  onSubmit: (payments: Array<{ method: 'CASH' | 'UPI'; amount: number; reference?: string }>) => Promise<void>;
}

export const PaymentModal: React.FC<PaymentModalProps> = ({
  isOpen,
  onClose,
  grandTotal,
  isProcessing,
  onSubmit,
}) => {
  const [paymentType, setPaymentType] = useState<PaymentType>('CASH');
  const [cashAmount, setCashAmount] = useState<string>(grandTotal.toString());
  const [upiAmount, setUpiAmount] = useState<string>('0');
  const [upiReference, setUpiReference] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleTypeChange = (type: PaymentType) => {
    setPaymentType(type);
    setErrorMessage(null);
    if (type === 'CASH') {
      setCashAmount(grandTotal.toString());
      setUpiAmount('0');
    } else if (type === 'UPI') {
      setCashAmount('0');
      setUpiAmount(grandTotal.toString());
    } else {
      // Split default 50/50
      const half = Math.floor(grandTotal / 2);
      setCashAmount(half.toString());
      setUpiAmount((grandTotal - half).toString());
    }
  };

  const handleCashChange = (val: string) => {
    setCashAmount(val);
    if (paymentType === 'SPLIT') {
      const c = parseFloat(val) || 0;
      const remaining = Math.max(0, grandTotal - c);
      setUpiAmount(remaining.toFixed(2));
    }
  };

  const handleUpiChange = (val: string) => {
    setUpiAmount(val);
    if (paymentType === 'SPLIT') {
      const u = parseFloat(val) || 0;
      const remaining = Math.max(0, grandTotal - u);
      setCashAmount(remaining.toFixed(2));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const c = parseFloat(cashAmount) || 0;
    const u = parseFloat(upiAmount) || 0;

    if (paymentType === 'CASH') {
      if (Math.abs(c - grandTotal) > 0.01) {
        setErrorMessage(`Cash payment must match the Grand Total (₹${grandTotal.toFixed(2)})`);
        return;
      }
    } else if (paymentType === 'UPI') {
      if (Math.abs(u - grandTotal) > 0.01) {
        setErrorMessage(`UPI payment must match the Grand Total (₹${grandTotal.toFixed(2)})`);
        return;
      }
    } else if (paymentType === 'SPLIT') {
      const totalTendered = c + u;
      if (Math.abs(totalTendered - grandTotal) > 0.01) {
        setErrorMessage(
          `Split payments (Cash + UPI) must equal exactly the Grand Total (₹${grandTotal.toFixed(2)}). Current total: ₹${totalTendered.toFixed(2)}`
        );
        return;
      }
    }

    const payments: Array<{ method: 'CASH' | 'UPI'; amount: number; reference?: string }> = [];

    if (paymentType === 'CASH' || (paymentType === 'SPLIT' && c > 0)) {
      payments.push({
        method: 'CASH',
        amount: paymentType === 'CASH' ? grandTotal : c,
      });
    }

    if (paymentType === 'UPI' || (paymentType === 'SPLIT' && u > 0)) {
      payments.push({
        method: 'UPI',
        amount: paymentType === 'UPI' ? grandTotal : u,
        reference: upiReference.trim() || undefined,
      });
    }

    try {
      await onSubmit(payments);
    } catch (err: any) {
      setErrorMessage(getErrorMessage(err));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-3 sm:p-4 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-md rounded-2xl sm:rounded-3xl bg-white p-4 sm:p-6 shadow-2xl max-h-[92vh] overflow-y-auto my-auto">
        <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
          <h3 className="text-lg font-bold text-zinc-900">Checkout & Payment</h3>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Grand Total Display */}
        <div className="my-3 sm:my-4 rounded-xl bg-zinc-900 p-3.5 sm:p-4 text-center text-white">
          <p className="text-xs uppercase tracking-wider text-zinc-400 font-semibold">Total Payable</p>
          <p className="text-2xl sm:text-3xl font-extrabold tracking-tight text-amber-400">
            {formatCurrency(grandTotal)}
          </p>
        </div>

        {/* Payment Type Selector */}
        <div className="grid grid-cols-3 gap-2 mb-3 sm:mb-4">
          <button
            type="button"
            onClick={() => handleTypeChange('CASH')}
            className={`flex flex-col items-center justify-center rounded-xl p-2.5 sm:p-3 border transition-all ${
              paymentType === 'CASH'
                ? 'border-amber-500 bg-amber-50/70 text-amber-950 font-bold shadow-sm'
                : 'border-zinc-200 bg-zinc-50 text-zinc-600 hover:bg-zinc-100 font-medium'
            }`}
          >
            <DollarSign className="h-5 w-5 mb-1 text-emerald-600" />
            <span className="text-xs">CASH</span>
          </button>

          <button
            type="button"
            onClick={() => handleTypeChange('UPI')}
            className={`flex flex-col items-center justify-center rounded-xl p-2.5 sm:p-3 border transition-all ${
              paymentType === 'UPI'
                ? 'border-amber-500 bg-amber-50/70 text-amber-950 font-bold shadow-sm'
                : 'border-zinc-200 bg-zinc-50 text-zinc-600 hover:bg-zinc-100 font-medium'
            }`}
          >
            <Smartphone className="h-5 w-5 mb-1 text-blue-600" />
            <span className="text-xs">UPI QR</span>
          </button>

          <button
            type="button"
            onClick={() => handleTypeChange('SPLIT')}
            className={`flex flex-col items-center justify-center rounded-xl p-2.5 sm:p-3 border transition-all ${
              paymentType === 'SPLIT'
                ? 'border-amber-500 bg-amber-50/70 text-amber-950 font-bold shadow-sm'
                : 'border-zinc-200 bg-zinc-50 text-zinc-600 hover:bg-zinc-100 font-medium'
            }`}
          >
            <Split className="h-5 w-5 mb-1 text-purple-600" />
            <span className="text-xs">SPLIT</span>
          </button>
        </div>

        {/* Payment Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          {(paymentType === 'CASH' || paymentType === 'SPLIT') && (
            <div>
              <label className="block text-xs font-semibold text-zinc-700 mb-1">
                Cash Amount (₹)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={cashAmount}
                onChange={(e) => handleCashChange(e.target.value)}
                required
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm font-semibold focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>
          )}

          {(paymentType === 'UPI' || paymentType === 'SPLIT') && (
            <div className="space-y-2">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  UPI Amount (₹)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={upiAmount}
                  onChange={(e) => handleUpiChange(e.target.value)}
                  required
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm font-semibold focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  UPI UTR / Reference No. (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. 423987123984"
                  value={upiReference}
                  onChange={(e) => setUpiReference(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                />
              </div>
            </div>
          )}

          {/* Operational Policy Note */}
          <div className="rounded-lg bg-zinc-50 border border-zinc-200 p-2.5 text-[11px] text-zinc-600 space-y-1">
            <div className="flex items-center gap-1.5 text-zinc-800 font-semibold">
              <AlertCircle className="h-3.5 w-3.5 text-amber-600" />
              <span>VIYON Payment Policy</span>
            </div>
            <ul className="list-disc pl-4 space-y-0.5 text-zinc-500">
              <li>CASH, UPI, and SPLIT payments are immediately marked as <strong>PAID</strong>.</li>
              <li>Official thermal receipt can be printed immediately upon checkout.</li>
            </ul>
          </div>

          {errorMessage && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700">
              {errorMessage}
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isProcessing}
              className="flex-1 rounded-xl border border-zinc-300 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isProcessing}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-amber-500 py-2.5 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400 active:scale-95 disabled:opacity-50"
            >
              {isProcessing ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-950 border-t-transparent" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Complete Checkout</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
