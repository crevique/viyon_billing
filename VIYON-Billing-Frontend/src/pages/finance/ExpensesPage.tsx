import React, { useState, useEffect } from 'react';
import {
  Wallet,
  Plus,
  Search,
  DollarSign,
  AlertTriangle,
  RotateCcw,
  X,
  CreditCard,
  Building,
  ArrowUpRight,
  ArrowDownRight,
  Lock,
  Unlock,
} from 'lucide-react';
import { Expense, DailyCashRegister } from '../../types';
import { financeService, CreateExpensePayload } from '../../services/financeService';
import { useAuthStore } from '../../stores/useAuthStore';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

export const ExpensesPage: React.FC = () => {
  const { role } = useAuthStore();
  const isOwner = role === 'OWNER' || role === 'ADMIN';

  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [totalActiveAmount, setTotalActiveAmount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [search, setSearch] = useState('');

  // Daily Cash Register State
  const [todayRegister, setTodayRegister] = useState<DailyCashRegister | null>(null);
  const [loadingRegister, setLoadingRegister] = useState(false);

  // Modals
  const [isExpenseModalOpen, setIsExpenseModalOpen] = useState(false);
  const [isVoidModalOpen, setIsVoidModalOpen] = useState(false);
  const [isShiftOpenModalOpen, setIsShiftOpenModalOpen] = useState(false);
  const [isShiftCloseModalOpen, setIsShiftCloseModalOpen] = useState(false);
  const [isMovementModalOpen, setIsMovementModalOpen] = useState(false);

  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);
  const [voidReason, setVoidReason] = useState('');

  // Expense Form State
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('TEA_SNACKS');
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState<'CASH' | 'UPI' | 'CARD'>('CASH');
  const [refNo, setRefNo] = useState('');
  const [description, setDescription] = useState('');

  // Cash Register Form State
  const [openingCash, setOpeningCash] = useState('1000');
  const [closingCash, setClosingCash] = useState('');
  const [movementType, setMovementType] = useState<'INFLOW' | 'OUTFLOW'>('INFLOW');
  const [movementAmount, setMovementAmount] = useState('');
  const [movementReason, setMovementReason] = useState('');

  useEffect(() => {
    loadExpenses();
    loadDailyRegister();
  }, [categoryFilter]);

  const loadExpenses = async () => {
    setLoading(true);
    try {
      const res = await financeService.getExpenses({
        category: categoryFilter || undefined,
        search: search.trim() || undefined,
      });
      setExpenses(res.items || []);
      setTotalActiveAmount(Number(res.total_active_amount || 0));
    } catch (err) {
      console.error('Failed to load expenses', err);
    } finally {
      setLoading(false);
    }
  };

  const loadDailyRegister = async () => {
    setLoadingRegister(true);
    try {
      const todayStr = new Date().toISOString().split('T')[0];
      const reg = await financeService.getTodayRegister(todayStr);
      setTodayRegister(reg);
    } catch {
      setTodayRegister(null);
    } finally {
      setLoadingRegister(false);
    }
  };

  const handleCreateExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(amount);
    if (!title.trim() || !val || val <= 0) {
      alert('Please enter a title and positive expense amount.');
      return;
    }

    try {
      const payload: CreateExpensePayload = {
        expense_title: title.trim(),
        category,
        amount: val,
        payment_method: method,
        reference_number: refNo.trim() || undefined,
        description: description.trim() || undefined,
      };

      await financeService.createExpense(payload);
      alert('Expense recorded.');
      setIsExpenseModalOpen(false);
      setTitle('');
      setAmount('');
      setRefNo('');
      setDescription('');
      loadExpenses();
      loadDailyRegister();
    } catch (err: any) {
      alert(`Expense failed: ${err.message || 'Unknown error'}`);
    }
  };

  const handleVoidExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedExpense || voidReason.trim().length < 3) return;

    try {
      await financeService.voidExpense(selectedExpense.id, voidReason.trim());
      alert('Expense voided.');
      setIsVoidModalOpen(false);
      setSelectedExpense(null);
      setVoidReason('');
      loadExpenses();
      loadDailyRegister();
    } catch (err: any) {
      alert(`Void failed: ${err.message || 'Unknown error'}`);
    }
  };

  // Cash Register Actions
  const handleOpenRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(openingCash);
    if (isNaN(val) || val < 0) return;

    try {
      await financeService.openCashRegister({ opening_cash: val });
      alert('Daily cash drawer opened.');
      setIsShiftOpenModalOpen(false);
      loadDailyRegister();
    } catch (err: any) {
      alert(`Failed to open drawer: ${err.message || 'Unknown error'}`);
    }
  };

  const handleCloseRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!todayRegister) return;
    const val = parseFloat(closingCash);
    if (isNaN(val) || val < 0) return;

    try {
      await financeService.closeCashRegister(todayRegister.id, { actual_closing_cash: val });
      alert('Daily cash register shift closed.');
      setIsShiftCloseModalOpen(false);
      loadDailyRegister();
    } catch (err: any) {
      alert(`Failed to close register: ${err.message || 'Unknown error'}`);
    }
  };

  const handleAddMovement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!todayRegister) return;
    const val = parseFloat(movementAmount);
    if (!val || val <= 0 || !movementReason.trim()) return;

    try {
      await financeService.addCashMovement(todayRegister.id, {
        movement_type: movementType,
        amount: val,
        reason: movementReason.trim(),
      });
      alert('Cash movement recorded.');
      setIsMovementModalOpen(false);
      setMovementAmount('');
      setMovementReason('');
      loadDailyRegister();
    } catch (err: any) {
      alert(`Movement failed: ${err.message || 'Unknown error'}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Expenses & Cash Register
          </h2>
          <p className="text-xs text-zinc-500">
            Store Owner Only: Track petty expenses, manage daily drawer opening floats, and reconcile closing cash variance.
          </p>
        </div>

        {isOwner && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsExpenseModalOpen(true)}
              className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95"
            >
              <Plus className="h-4 w-4" />
              <span>Record Expense</span>
            </button>
          </div>
        )}
      </div>

      {/* Daily Cash Drawer Shift Status Card */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-zinc-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Wallet className="h-5 w-5 text-amber-500" />
            <h3 className="text-sm font-bold text-zinc-900">Today's Cash Register Drawer</h3>
          </div>

          {!todayRegister ? (
            <button
              onClick={() => setIsShiftOpenModalOpen(true)}
              className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-500"
            >
              <Unlock className="h-3.5 w-3.5" />
              <span>Open Cash Drawer</span>
            </button>
          ) : !todayRegister.is_closed ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsMovementModalOpen(true)}
                className="rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
              >
                Cash In/Out
              </button>
              <button
                onClick={() => {
                  setClosingCash(todayRegister.expected_closing_cash?.toString() || '');
                  setIsShiftCloseModalOpen(true);
                }}
                className="flex items-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1 text-xs font-bold text-white hover:bg-zinc-800"
              >
                <Lock className="h-3.5 w-3.5" />
                <span>Close Shift</span>
              </button>
            </div>
          ) : (
            <span className="rounded bg-zinc-100 text-zinc-600 font-bold px-2 py-0.5 text-xs">
              SHIFT CLOSED
            </span>
          )}
        </div>

        {todayRegister ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3 text-center">
            <div className="rounded-xl bg-zinc-50 p-2.5">
              <span className="text-[10px] text-zinc-400 font-semibold uppercase">Opening Float</span>
              <p className="text-sm font-bold text-zinc-900 mt-0.5">
                {formatCurrency(todayRegister.opening_cash)}
              </p>
            </div>
            <div className="rounded-xl bg-zinc-50 p-2.5">
              <span className="text-[10px] text-zinc-400 font-semibold uppercase">Cash Sales (+)</span>
              <p className="text-sm font-bold text-emerald-600 mt-0.5">
                +{formatCurrency(todayRegister.cash_sales)}
              </p>
            </div>
            <div className="rounded-xl bg-zinc-50 p-2.5">
              <span className="text-[10px] text-zinc-400 font-semibold uppercase">Cash Expenses (-)</span>
              <p className="text-sm font-bold text-rose-600 mt-0.5">
                -{formatCurrency(todayRegister.cash_expenses)}
              </p>
            </div>
            <div className="rounded-xl bg-zinc-50 p-2.5">
              <span className="text-[10px] text-zinc-400 font-semibold uppercase">Expected Closing</span>
              <p className="text-sm font-black text-amber-600 mt-0.5">
                {formatCurrency(todayRegister.expected_closing_cash)}
              </p>
            </div>
            <div className="rounded-xl bg-zinc-50 p-2.5">
              <span className="text-[10px] text-zinc-400 font-semibold uppercase">Variance</span>
              <p className="text-sm font-bold text-zinc-900 mt-0.5">
                {todayRegister.cash_difference !== null && todayRegister.cash_difference !== undefined
                  ? formatCurrency(todayRegister.cash_difference)
                  : 'Pending Close'}
              </p>
            </div>
          </div>
        ) : (
          <p className="py-2 text-xs text-zinc-400 italic">
            Cash register is not yet opened for today. Click "Open Cash Drawer" to specify the morning cash float.
          </p>
        )}
      </div>

      {/* Expenses Table Header & Search */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              placeholder="Search expenses by title or reference number..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-zinc-200 bg-zinc-50 pl-9 pr-4 py-2 text-xs focus:border-amber-500 focus:bg-white focus:outline-none"
            />
          </div>

          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-700 focus:border-amber-500 focus:outline-none"
          >
            <option value="">All Categories</option>
            <option value="TEA_SNACKS">Tea & Refreshments</option>
            <option value="ELECTRICITY">Electricity & Utilities</option>
            <option value="RENT">Store Rent</option>
            <option value="PACKAGING">Packaging & Bags</option>
            <option value="CLEANING">Cleaning & Maintenance</option>
            <option value="SALARY_ADVANCE">Staff Advance</option>
            <option value="OTHER">Other Operational</option>
          </select>
        </div>
      </div>

      {/* Expenses Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading expenses...</p>
          </div>
        ) : expenses.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            No expenses recorded.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">Expense Title</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Date & Time</th>
                  <th className="py-3 px-4">Payment Method</th>
                  <th className="py-3 px-4">Logged By</th>
                  <th className="py-3 px-4 text-right">Amount</th>
                  <th className="py-3 px-4">Status</th>
                  {isOwner && <th className="py-3 px-4 text-center">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {expenses.map((exp) => (
                  <tr key={exp.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-zinc-900">
                      <div>
                        <span>{exp.expense_title}</span>
                        {exp.description && (
                          <p className="text-[11px] text-zinc-400 font-normal">{exp.description}</p>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="rounded bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold text-zinc-700">
                        {exp.category}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-zinc-500">{formatDateTime(exp.expense_date)}</td>
                    <td className="py-3 px-4 font-medium text-zinc-700">{exp.payment_method}</td>
                    <td className="py-3 px-4 text-zinc-500">{exp.created_by_user_name || 'Owner'}</td>
                    <td className="py-3 px-4 text-right font-black text-rose-600">
                      -{formatCurrency(exp.amount)}
                    </td>
                    <td className="py-3 px-4">
                      {exp.is_voided ? (
                        <span className="rounded bg-rose-50 border border-rose-200 text-rose-700 font-bold px-2 py-0.5 text-[10px]">
                          VOIDED
                        </span>
                      ) : (
                        <span className="rounded bg-emerald-50 border border-emerald-200 text-emerald-700 font-bold px-2 py-0.5 text-[10px]">
                          ACTIVE
                        </span>
                      )}
                    </td>
                    {isOwner && (
                      <td className="py-3 px-4 text-center">
                        {!exp.is_voided && (
                          <button
                            onClick={() => {
                              setSelectedExpense(exp);
                              setIsVoidModalOpen(true);
                            }}
                            className="rounded px-2 py-1 text-[11px] font-semibold text-rose-600 hover:bg-rose-50"
                          >
                            Void
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

      {/* Record Expense Modal */}
      {isExpenseModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-3 sm:p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-4 sm:p-6 shadow-2xl max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <h3 className="text-base font-bold text-zinc-900">Record Store Expense</h3>
              <button
                onClick={() => setIsExpenseModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreateExpense} className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Expense Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Evening staff tea and biscuits"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Category *
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
                  >
                    <option value="TEA_SNACKS">Tea & Refreshments</option>
                    <option value="ELECTRICITY">Electricity & Bills</option>
                    <option value="RENT">Store Rent</option>
                    <option value="PACKAGING">Packaging Covers & Bags</option>
                    <option value="CLEANING">Cleaning & Housekeeping</option>
                    <option value="SALARY_ADVANCE">Staff Salary Advance</option>
                    <option value="OTHER">Other Expense</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Amount (₹) *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    placeholder="e.g. 150.00"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs font-bold focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Disbursed via Payment Method
                </label>
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value as any)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
                >
                  <option value="CASH">CASH (Deducted from drawer)</option>
                  <option value="UPI">UPI</option>
                  <option value="CARD">Debit/Credit Card</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Bill / Voucher / Reference Number
                </label>
                <input
                  type="text"
                  placeholder="Optional reference"
                  value={refNo}
                  onChange={(e) => setRefNo(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsExpenseModalOpen(false)}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-amber-500 py-2 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400"
                >
                  Record Expense
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Void Expense Modal */}
      {isVoidModalOpen && selectedExpense && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-3 sm:p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-4 sm:p-6 shadow-2xl max-h-[92vh] overflow-y-auto">
            <h3 className="text-base font-bold text-zinc-900 mb-2">Void Expense Voucher</h3>
            <p className="text-xs text-zinc-600 mb-4">
              Voiding <strong>{selectedExpense.expense_title}</strong> ({formatCurrency(selectedExpense.amount)}).
              This action is preserved in audit logs.
            </p>

            <form onSubmit={handleVoidExpense} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Mandatory Void Reason *
                </label>
                <textarea
                  rows={2}
                  required
                  placeholder="e.g. Duplicate entry made by mistake"
                  value={voidReason}
                  onChange={(e) => setVoidReason(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-rose-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setIsVoidModalOpen(false)}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Back
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-rose-600 py-2 text-xs font-bold text-white shadow-md hover:bg-rose-500"
                >
                  Confirm Void
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Open Cash Drawer Modal */}
      {isShiftOpenModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-3 sm:p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-sm rounded-2xl bg-white p-4 sm:p-6 shadow-2xl max-h-[92vh] overflow-y-auto">
            <h3 className="text-base font-bold text-zinc-900 mb-2">Open Daily Cash Drawer</h3>
            <p className="text-xs text-zinc-500 mb-4">
              Enter the starting physical cash float in the cash drawer this morning.
            </p>

            <form onSubmit={handleOpenRegister} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Opening Float (₹) *
                </label>
                <input
                  type="number"
                  step="1"
                  min="0"
                  required
                  value={openingCash}
                  onChange={(e) => setOpeningCash(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm font-black text-zinc-900 focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setIsShiftOpenModalOpen(false)}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-emerald-600 py-2 text-xs font-bold text-white shadow-md hover:bg-emerald-500"
                >
                  Open Drawer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Close Cash Drawer Modal */}
      {isShiftCloseModalOpen && todayRegister && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-3 sm:p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-sm rounded-2xl bg-white p-4 sm:p-6 shadow-2xl max-h-[92vh] overflow-y-auto">
            <h3 className="text-base font-bold text-zinc-900 mb-2">Close Daily Shift</h3>
            <p className="text-xs text-zinc-500 mb-2">
              Expected physical cash in drawer: <strong>{formatCurrency(todayRegister.expected_closing_cash)}</strong>
            </p>

            <form onSubmit={handleCloseRegister} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Actual Physical Cash Count (₹) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={closingCash}
                  onChange={(e) => setClosingCash(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm font-black text-zinc-900 focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setIsShiftCloseModalOpen(false)}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-zinc-900 py-2 text-xs font-bold text-white shadow-md hover:bg-zinc-800"
                >
                  Lock Shift
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Auxiliary Cash Inflow/Outflow Modal */}
      {isMovementModalOpen && todayRegister && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-3 sm:p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-sm rounded-2xl bg-white p-4 sm:p-6 shadow-2xl max-h-[92vh] overflow-y-auto">
            <h3 className="text-base font-bold text-zinc-900 mb-3">Auxiliary Cash Movement</h3>

            <form onSubmit={handleAddMovement} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">Movement Type</label>
                <select
                  value={movementType}
                  onChange={(e) => setMovementType(e.target.value as any)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800"
                >
                  <option value="INFLOW">Cash Inflow (e.g. Owner injected change float)</option>
                  <option value="OUTFLOW">Cash Outflow (e.g. Bank deposit / Owner withdrawal)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">Amount (₹) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={movementAmount}
                  onChange={(e) => setMovementAmount(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs font-bold"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">Reason / Purpose *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Deposited cash to Indian Bank"
                  value={movementReason}
                  onChange={(e) => setMovementReason(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsMovementModalOpen(false)}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-amber-500 py-2 text-xs font-bold text-zinc-950"
                >
                  Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
