import React, { useState, useEffect } from 'react';
import { Expense, ExpenseCategory, PaymentMethod, formatINR } from './types';

interface ExpenseManagementProps {
  onRefreshOverview?: () => void;
}

export const ExpenseManagement: React.FC<ExpenseManagementProps> = ({ onRefreshOverview }) => {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [totalActive, setTotalActive] = useState<number | string>(0);
  const [totalVoided, setTotalVoided] = useState<number | string>(0);
  const [loading, setLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [methodFilter, setMethodFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [showVoidModal, setShowVoidModal] = useState(false);
  const [selectedExpense, setSelectedExpense] = useState<Expense | null>(null);
  const [voidReason, setVoidReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // New Expense Form State
  const [newTitle, setNewTitle] = useState('');
  const [newCategory, setNewCategory] = useState<ExpenseCategory>('SHOP_SUPPLIES');
  const [newAmount, setNewAmount] = useState('');
  const [newMethod, setNewMethod] = useState<PaymentMethod>('CASH');
  const [newDate, setNewDate] = useState(new Date().toISOString().split('T')[0]);
  const [newRef, setNewRef] = useState('');
  const [newDesc, setNewDesc] = useState('');

  const fetchExpenses = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (categoryFilter) params.append('category', categoryFilter);
      if (methodFilter) params.append('payment_method', methodFilter);
      if (search) params.append('search', search);

      const res = await fetch(`/api/v1/expenses?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setExpenses(data.items || []);
        setTotalActive(data.total_active_amount || 0);
        setTotalVoided(data.total_voided_amount || 0);
      }
    } catch (err) {
      console.error('Failed to load expenses', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExpenses();
  }, [categoryFilter, methodFilter]);

  const handleAddExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newAmount || parseFloat(newAmount) <= 0) return;

    setActionLoading(true);
    try {
      const res = await fetch('/api/v1/expenses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expense_title: newTitle.trim(),
          category: newCategory,
          amount: parseFloat(newAmount),
          payment_method: newMethod,
          expense_date: new Date(newDate).toISOString(),
          reference_number: newRef.trim() || null,
          description: newDesc.trim() || null,
        }),
      });

      if (res.ok) {
        setShowAddModal(false);
        setNewTitle('');
        setNewAmount('');
        setNewRef('');
        setNewDesc('');
        fetchExpenses();
        if (onRefreshOverview) onRefreshOverview();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to record expense.');
      }
    } catch (err) {
      alert('Error connecting to server.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleVoidExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedExpense || !voidReason.trim()) return;

    setActionLoading(true);
    try {
      const res = await fetch(`/api/v1/expenses/${selectedExpense.id}/void`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ void_reason: voidReason.trim() }),
      });

      if (res.ok) {
        setShowVoidModal(false);
        setSelectedExpense(null);
        setVoidReason('');
        fetchExpenses();
        if (onRefreshOverview) onRefreshOverview();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to void expense.');
      }
    } catch (err) {
      alert('Error connecting to server.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      {/* Header with Title & Action */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-5 border-b border-gray-100 gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Expense Management</h2>
          <p className="text-xs text-gray-500 mt-0.5">Track, audit, and categorize physical store operational costs</p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center justify-center px-4 py-2 border border-transparent rounded-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm transition"
        >
          <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
          Record Expense
        </button>
      </div>

      {/* Summary Chips */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 my-5">
        <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3.5 flex justify-between items-center">
          <div>
            <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">Active Store Expenses</span>
            <p className="text-lg font-bold text-emerald-900 mt-0.5">{formatINR(totalActive)}</p>
          </div>
          <span className="px-2 py-1 text-xs font-medium bg-emerald-200/60 text-emerald-800 rounded">Audited</span>
        </div>

        <div className="bg-red-50 border border-red-100 rounded-lg p-3.5 flex justify-between items-center">
          <div>
            <span className="text-xs font-semibold text-red-800 uppercase tracking-wider">Voided Expenses</span>
            <p className="text-lg font-bold text-red-900 mt-0.5">{formatINR(totalVoided)}</p>
          </div>
          <span className="px-2 py-1 text-xs font-medium bg-red-200/60 text-red-800 rounded">Excluded</span>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-col md:flex-row gap-3 items-center justify-between pb-4">
        <div className="flex flex-1 w-full md:w-auto gap-2">
          <input
            type="text"
            placeholder="Search by title, reference #, note..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchExpenses()}
            className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:ring-indigo-500 focus:border-indigo-500"
          />
          <button
            onClick={fetchExpenses}
            className="px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium"
          >
            Search
          </button>
        </div>

        <div className="flex w-full md:w-auto gap-2">
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white"
          >
            <option value="">All Categories</option>
            <option value="RENT">Rent</option>
            <option value="ELECTRICITY">Electricity</option>
            <option value="SALARY">Salary</option>
            <option value="SHOP_SUPPLIES">Shop Supplies</option>
            <option value="MAINTENANCE">Maintenance</option>
            <option value="PACKAGING">Packaging</option>
            <option value="MARKETING">Marketing</option>
            <option value="TRANSPORT">Transport</option>
            <option value="OTHER">Other</option>
          </select>

          <select
            value={methodFilter}
            onChange={(e) => setMethodFilter(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white"
          >
            <option value="">All Methods</option>
            <option value="CASH">Cash</option>
            <option value="UPI">UPI</option>
            <option value="CARD">Card</option>
          </select>
        </div>
      </div>

      {/* Expenses Table */}
      <div className="overflow-x-auto border border-gray-200 rounded-lg">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-gray-500 text-xs font-semibold uppercase tracking-wider">
            <tr>
              <th className="px-4 py-3 text-left">Date</th>
              <th className="px-4 py-3 text-left">Title & Category</th>
              <th className="px-4 py-3 text-left">Payment Method</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3 text-center">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                  Loading expenses...
                </td>
              </tr>
            ) : expenses.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                  No expense records match criteria.
                </td>
              </tr>
            ) : (
              expenses.map((exp) => (
                <tr key={exp.id} className={exp.is_voided ? 'bg-red-50/30' : 'hover:bg-gray-50/60'}>
                  <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                    {new Date(exp.expense_date).toLocaleDateString('en-IN', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-gray-900">{exp.expense_title}</div>
                    <div className="text-xs text-indigo-600 font-medium">{exp.category}</div>
                    {exp.description && <div className="text-xs text-gray-500 truncate max-w-xs">{exp.description}</div>}
                  </td>
                  <td className="px-4 py-3 text-gray-700 whitespace-nowrap">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                      {exp.payment_method}
                    </span>
                    {exp.reference_number && (
                      <span className="block text-xs text-gray-400 mt-0.5">Ref: {exp.reference_number}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-bold text-gray-900 whitespace-nowrap">
                    {formatINR(exp.amount)}
                  </td>
                  <td className="px-4 py-3 text-center whitespace-nowrap">
                    {exp.is_voided ? (
                      <div>
                        <span className="px-2 py-0.5 text-xs font-semibold bg-red-100 text-red-800 rounded-full">
                          Voided
                        </span>
                        {exp.void_reason && (
                          <div className="text-2xs text-red-600 mt-0.5 truncate max-w-xs" title={exp.void_reason}>
                            {exp.void_reason}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-100 text-emerald-800 rounded-full">
                        Active
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    {!exp.is_voided && (
                      <button
                        onClick={() => {
                          setSelectedExpense(exp);
                          setShowVoidModal(true);
                        }}
                        className="text-xs font-semibold text-red-600 hover:text-red-800 ml-2"
                      >
                        Void
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Record Expense Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Record New Expense</h3>
            <form onSubmit={handleAddExpense} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700">Expense Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Monthly Electricity Bill"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700">Category *</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value as ExpenseCategory)}
                    className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2 bg-white"
                  >
                    <option value="RENT">Rent</option>
                    <option value="ELECTRICITY">Electricity</option>
                    <option value="WATER">Water</option>
                    <option value="INTERNET">Internet</option>
                    <option value="SALARY">Salary</option>
                    <option value="TRANSPORT">Transport</option>
                    <option value="PACKAGING">Packaging</option>
                    <option value="MAINTENANCE">Maintenance</option>
                    <option value="SHOP_SUPPLIES">Shop Supplies</option>
                    <option value="MARKETING">Marketing</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700">Amount (INR) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    placeholder="0.00"
                    value={newAmount}
                    onChange={(e) => setNewAmount(e.target.value)}
                    className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700">Payment Method *</label>
                  <select
                    value={newMethod}
                    onChange={(e) => setNewMethod(e.target.value as PaymentMethod)}
                    className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2 bg-white"
                  >
                    <option value="CASH">Cash</option>
                    <option value="UPI">UPI</option>
                    <option value="CARD">Card</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700">Expense Date *</label>
                  <input
                    type="date"
                    required
                    value={newDate}
                    onChange={(e) => setNewDate(e.target.value)}
                    className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2 bg-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700">Reference / UTR Number</label>
                <input
                  type="text"
                  placeholder="Optional UPI UTR or Cheque #"
                  value={newRef}
                  onChange={(e) => setNewRef(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700">Description / Notes</label>
                <textarea
                  rows={2}
                  placeholder="Additional context..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg font-semibold shadow-sm"
                >
                  {actionLoading ? 'Saving...' : 'Record Expense'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Void Modal */}
      {showVoidModal && selectedExpense && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-xl">
            <h3 className="text-lg font-bold text-gray-900 mb-2">Void Expense</h3>
            <p className="text-xs text-gray-600 mb-4">
              Voiding <span className="font-semibold">{selectedExpense.expense_title}</span> ({formatINR(selectedExpense.amount)})
              will permanently exclude it from operational cost totals while retaining an immutable audit trail.
            </p>

            <form onSubmit={handleVoidExpense} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-700">Mandatory Void Reason *</label>
                <textarea
                  required
                  rows={3}
                  placeholder="Reason for voiding (e.g. Duplicate entry, Incorrect bill amount)..."
                  value={voidReason}
                  onChange={(e) => setVoidReason(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-lg p-2 focus:ring-red-500 focus:border-red-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowVoidModal(false);
                    setSelectedExpense(null);
                  }}
                  className="px-4 py-2 text-sm text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading || !voidReason.trim()}
                  className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg font-semibold shadow-sm"
                >
                  {actionLoading ? 'Voiding...' : 'Confirm Void'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
