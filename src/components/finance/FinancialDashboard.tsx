import React, { useState, useEffect } from 'react';
import { FinancialOverview, formatINR } from './types';
import { ProfitLossCard } from './ProfitLossCard';
import { ExpenseManagement } from './ExpenseManagement';
import { CashManagementModal } from './CashManagementModal';
import { FinancialReports } from './FinancialReports';

export const FinancialDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'OVERVIEW' | 'EXPENSES' | 'REPORTS'>('OVERVIEW');
  const [preset, setPreset] = useState<string>('today');
  const [overview, setOverview] = useState<FinancialOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [showCashModal, setShowCashModal] = useState(false);

  const fetchOverview = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/finance/overview?preset=${preset}`);
      if (res.ok) {
        setOverview(await res.json());
      }
    } catch (err) {
      console.error('Failed to load overview', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOverview();
  }, [preset]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 font-sans">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-gray-200">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-black text-gray-900 tracking-tight">Financial Management</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-100 text-indigo-800">
              VIYON STORE
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Store Performance, Daily Sales, Expenses, Cash Reconciliation & Audited Reports
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Quick Cash Drawer Button */}
          <button
            onClick={() => setShowCashModal(true)}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 bg-white hover:bg-gray-50 shadow-sm transition"
          >
            <svg className="w-4 h-4 mr-2 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Daily Cash Drawer
            {overview?.cash_register_status && (
              <span
                className={`ml-2 w-2 h-2 rounded-full ${
                  overview.cash_register_status === 'OPEN'
                    ? 'bg-emerald-500'
                    : overview.cash_register_status === 'CLOSED'
                    ? 'bg-gray-400'
                    : 'bg-amber-400'
                }`}
              />
            )}
          </button>

          {/* Period Preset Pills */}
          <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 text-xs font-semibold">
            {(['today', 'yesterday', 'this_week', 'this_month', 'previous_month'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPreset(p)}
                className={`px-3 py-1.5 rounded-md transition ${
                  preset === p ? 'bg-white text-indigo-700 shadow-sm font-bold' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {p.replace('_', ' ').toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Tab Navigation */}
      <div className="flex border-b border-gray-200 text-sm font-semibold">
        <button
          onClick={() => setActiveTab('OVERVIEW')}
          className={`py-3 px-6 border-b-2 transition ${
            activeTab === 'OVERVIEW'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Executive Overview
        </button>
        <button
          onClick={() => setActiveTab('EXPENSES')}
          className={`py-3 px-6 border-b-2 transition ${
            activeTab === 'EXPENSES'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Expense Tracking
        </button>
        <button
          onClick={() => setActiveTab('REPORTS')}
          className={`py-3 px-6 border-b-2 transition ${
            activeTab === 'REPORTS'
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Reports & Export
        </button>
      </div>

      {/* TAB CONTENT: Overview */}
      {activeTab === 'OVERVIEW' && (
        <div className="space-y-6">
          {loading || !overview ? (
            <div className="py-20 text-center text-gray-400 font-medium">Loading executive financial analytics...</div>
          ) : (
            <>
              {/* Top KPI Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                {/* Net Sales */}
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 hover:shadow-md transition">
                  <div className="flex items-center justify-between text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    <span>Net Realized Sales</span>
                    <span className="text-gray-400">{overview.completed_bills_count} Bills</span>
                  </div>
                  <p className="text-2xl font-black text-gray-900 mt-2">{formatINR(overview.net_sales)}</p>
                  <p className="text-xs text-gray-500 mt-1">Excludes {overview.cancelled_bills_count} cancelled bills</p>
                </div>

                {/* Collections */}
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 hover:shadow-md transition">
                  <div className="flex items-center justify-between text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    <span>Confirmed Collections</span>
                    <span className="text-emerald-600 font-bold">100% Realized</span>
                  </div>
                  <p className="text-2xl font-black text-emerald-700 mt-2">
                    {formatINR(overview.total_confirmed_collections)}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Cash: {formatINR(overview.cash_collections)} | UPI: {formatINR(overview.upi_collections)}
                  </p>
                </div>

                {/* Operating Expenses */}
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 hover:shadow-md transition">
                  <div className="flex items-center justify-between text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    <span>Store Expenses</span>
                    <span className="text-red-600 font-bold">Operating</span>
                  </div>
                  <p className="text-2xl font-black text-red-600 mt-2">{formatINR(overview.total_operating_expenses)}</p>
                  <p className="text-xs text-gray-500 mt-1">Active non-voided store costs</p>
                </div>

                {/* Net Cash Flow */}
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 hover:shadow-md transition">
                  <div className="flex items-center justify-between text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    <span>Net Cash Flow</span>
                    <span className="text-blue-600 font-bold">Physical Drawer</span>
                  </div>
                  <p className="text-2xl font-black text-blue-900 mt-2">{formatINR(overview.net_cash_flow)}</p>
                  <p className="text-xs text-gray-500 mt-1">Cash in hand variance</p>
                </div>
              </div>

              {/* Pending UPI Alert Banner */}
              {Number(overview.pending_upi_amount) > 0 && (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div>
                      <p className="text-sm font-bold text-amber-900">
                        {formatINR(overview.pending_upi_amount)} Pending in Unconfirmed UPI Payments
                      </p>
                      <p className="text-xs text-amber-700 mt-0.5">
                        In accordance with store policy, pending UPI is isolated and not counted towards realized revenue or collections.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Profit and Loss Card */}
              <ProfitLossCard report={overview.profit_loss} />
            </>
          )}
        </div>
      )}

      {/* TAB CONTENT: Expenses */}
      {activeTab === 'EXPENSES' && <ExpenseManagement onRefreshOverview={fetchOverview} />}

      {/* TAB CONTENT: Reports */}
      {activeTab === 'REPORTS' && <FinancialReports preset={preset} />}

      {/* Daily Cash Drawer Modal */}
      <CashManagementModal
        isOpen={showCashModal}
        onClose={() => setShowCashModal(false)}
        onSuccess={fetchOverview}
      />
    </div>
  );
};
