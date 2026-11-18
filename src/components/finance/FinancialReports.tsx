import React, { useState, useEffect } from 'react';
import { DailySalesSummary, CashFlowSummary, formatINR } from './types';

interface FinancialReportsProps {
  preset: string;
}

export const FinancialReports: React.FC<FinancialReportsProps> = ({ preset }) => {
  const [salesSummary, setSalesSummary] = useState<DailySalesSummary | null>(null);
  const [cashFlow, setCashFlow] = useState<CashFlowSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState<'PDF' | 'EXCEL' | null>(null);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const [resSales, resCash] = await Promise.all([
        fetch('/api/v1/finance/daily-summary'),
        fetch(`/api/v1/finance/cash-flow?preset=${preset}`),
      ]);
      if (resSales.ok) setSalesSummary(await resSales.json());
      if (resCash.ok) setCashFlow(await resCash.json());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [preset]);

  const handleDownload = async (type: 'PDF' | 'EXCEL') => {
    setExportLoading(type);
    try {
      const endpoint =
        type === 'PDF'
          ? `/api/v1/finance/reports/export/pdf?preset=${preset}`
          : `/api/v1/finance/reports/export/excel?preset=${preset}`;
      const res = await fetch(endpoint);
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = type === 'PDF' ? `VIYON-Report-${preset}.pdf` : `VIYON-Report-${preset}.xlsx`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      } else {
        alert('Failed to generate export file.');
      }
    } catch {
      alert('Error downloading report.');
    } finally {
      setExportLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner with Exports */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Financial Reports & Exports</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Download certified PDF and multi-sheet Excel statements with store branding
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => handleDownload('PDF')}
            disabled={exportLoading !== null}
            className="inline-flex items-center px-4 py-2 border border-red-200 rounded-lg text-sm font-semibold text-red-700 bg-red-50 hover:bg-red-100 transition shadow-sm"
          >
            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            {exportLoading === 'PDF' ? 'Exporting PDF...' : 'Download PDF'}
          </button>

          <button
            onClick={() => handleDownload('EXCEL')}
            disabled={exportLoading !== null}
            className="inline-flex items-center px-4 py-2 border border-emerald-200 rounded-lg text-sm font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 transition shadow-sm"
          >
            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            {exportLoading === 'EXCEL' ? 'Exporting Excel...' : 'Download Excel'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="p-12 text-center text-gray-500">Loading reports data...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Daily Sales Reconciliation */}
          {salesSummary && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                <h3 className="text-base font-bold text-gray-900">Sales & Tax Ledger</h3>
                <span className="text-xs text-gray-500 font-medium">Date: {salesSummary.business_date}</span>
              </div>

              <div className="divide-y divide-gray-100 text-xs mt-3">
                <div className="py-2.5 flex justify-between">
                  <span className="text-gray-500">Completed Bills</span>
                  <span className="font-bold text-gray-900">{salesSummary.completed_bills_count}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-gray-500">Cancelled Bills (Excluded)</span>
                  <span className="font-bold text-red-600">{salesSummary.cancelled_bills_count}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-gray-500">Gross Sales</span>
                  <span className="font-medium text-gray-900">{formatINR(salesSummary.gross_sales)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-gray-500">Total Discounts Given</span>
                  <span className="font-medium text-red-600">-{formatINR(salesSummary.total_discounts)}</span>
                </div>
                <div className="py-2.5 flex justify-between bg-gray-50 px-2 rounded">
                  <span className="font-bold text-gray-800">Net Realized Sales</span>
                  <span className="font-black text-gray-900">{formatINR(salesSummary.net_sales)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-gray-500">GST / Tax Amount</span>
                  <span className="font-medium text-gray-900">{formatINR(salesSummary.total_tax)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-gray-500">Confirmed Cash Collections</span>
                  <span className="font-bold text-emerald-700">{formatINR(salesSummary.confirmed_cash_collections)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-gray-500">Confirmed UPI Collections</span>
                  <span className="font-bold text-blue-700">{formatINR(salesSummary.confirmed_upi_collections)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-amber-700 font-medium">Pending UPI Payments ({salesSummary.pending_upi_count})</span>
                  <span className="font-bold text-amber-800">{formatINR(salesSummary.pending_upi_amount)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-gray-500">Outstanding Customer Balance</span>
                  <span className="font-bold text-gray-900">{formatINR(salesSummary.outstanding_customer_balance)}</span>
                </div>
              </div>
            </div>
          )}

          {/* Cash Flow Reconciliation */}
          {cashFlow && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                <h3 className="text-base font-bold text-gray-900">Physical Cash Flow</h3>
                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                  {cashFlow.reconciliation_status}
                </span>
              </div>

              <div className="divide-y divide-gray-100 text-xs mt-3">
                <div className="py-2.5 flex justify-between">
                  <span className="text-gray-500">Opening Cash Balance</span>
                  <span className="font-medium text-gray-900">{formatINR(cashFlow.opening_cash)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-emerald-700">+ Confirmed Cash Sales</span>
                  <span className="font-bold text-emerald-800">{formatINR(cashFlow.cash_sales)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-blue-700">+ Auxiliary Cash Inflows</span>
                  <span className="font-bold text-blue-800">{formatINR(cashFlow.other_cash_inflow)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-red-600">- Cash Expenses Paid</span>
                  <span className="font-bold text-red-600">-{formatINR(cashFlow.cash_expenses)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="text-red-600">- Auxiliary Cash Withdrawals</span>
                  <span className="font-bold text-red-600">-{formatINR(cashFlow.other_cash_outflow)}</span>
                </div>
                <div className="py-2.5 flex justify-between bg-indigo-50/50 px-2 rounded">
                  <span className="font-bold text-indigo-900">Net Cash Inflow / Outflow</span>
                  <span className="font-black text-indigo-950">{formatINR(cashFlow.net_cash_flow)}</span>
                </div>
                <div className="py-2.5 flex justify-between">
                  <span className="font-bold text-gray-700">Expected Closing Cash</span>
                  <span className="font-black text-gray-900">{formatINR(cashFlow.expected_closing_cash)}</span>
                </div>
                {cashFlow.actual_closing_cash !== null && (
                  <>
                    <div className="py-2.5 flex justify-between">
                      <span className="font-bold text-gray-700">Actual Physical Count</span>
                      <span className="font-black text-gray-900">{formatINR(cashFlow.actual_closing_cash)}</span>
                    </div>
                    <div className="py-2.5 flex justify-between bg-gray-50 px-2 rounded">
                      <span className="font-bold text-gray-800">Cash Difference</span>
                      <span
                        className={`font-black ${
                          Number(cashFlow.cash_difference || 0) < 0 ? 'text-red-600' : 'text-emerald-700'
                        }`}
                      >
                        {formatINR(cashFlow.cash_difference)}
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
