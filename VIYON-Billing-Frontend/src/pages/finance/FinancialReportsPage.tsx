import React, { useState, useEffect } from 'react';
import {
  Calendar,
  RefreshCw,
  Download,
  AlertCircle,
  Receipt,
  ShoppingBag,
  ArrowUpRight,
  ArrowDownRight,
  Scale,
} from 'lucide-react';
import { SalesReportResponse, ExpenseReportResponse } from '../../types';
import { financeService } from '../../services/financeService';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

export const FinancialReportsPage: React.FC = () => {
  const [preset, setPreset] = useState<string>('today');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [salesData, setSalesData] = useState<SalesReportResponse | null>(null);
  const [expenseData, setExpenseData] = useState<ExpenseReportResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [pdfDownloading, setPdfDownloading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (preset !== 'custom') {
      loadReports(preset);
    }
  }, [preset]);

  const loadReports = async (targetPreset: string, sDate?: string, eDate?: string) => {
    setLoading(true);
    setErrorMessage(null);
    setValidationError(null);

    try {
      const params: { preset?: string; start_date?: string; end_date?: string } = {
        preset: targetPreset,
      };

      if (targetPreset === 'custom') {
        if (!sDate || !eDate) {
          setLoading(false);
          return;
        }
        if (sDate > eDate) {
          setValidationError('End date cannot be earlier than start date.');
          setLoading(false);
          return;
        }
        params.start_date = sDate;
        params.end_date = eDate;
      }

      const [salesRes, expenseRes] = await Promise.all([
        financeService.getSalesReport(params),
        financeService.getExpenseReport(params),
      ]);

      setSalesData(salesRes);
      setExpenseData(expenseRes);
    } catch (err: any) {
      console.error('Failed to load financial reports', err);
      setErrorMessage(
        err?.response?.data?.detail || 'Failed to load financial records. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handlePresetChange = (newPreset: string) => {
    setPreset(newPreset);
    setValidationError(null);
    if (newPreset !== 'custom') {
      loadReports(newPreset);
    }
  };

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!startDate || !endDate) {
      setValidationError('Please select both start and end dates.');
      return;
    }
    if (startDate > endDate) {
      setValidationError('End date cannot be earlier than start date.');
      return;
    }
    loadReports('custom', startDate, endDate);
  };

  const handleDownloadPdf = async () => {
    if (pdfDownloading) return;
    setPdfDownloading(true);
    try {
      await financeService.downloadPdfReport({
        preset,
        start_date: preset === 'custom' ? startDate : undefined,
        end_date: preset === 'custom' ? endDate : undefined,
      });
    } catch (err: any) {
      console.error('PDF download failed', err);
      alert('Failed to download PDF report. Please try again.');
    } finally {
      setPdfDownloading(false);
    }
  };

  // Helper to format the period header (e.g. "14 November 2026" or "01 November 2026 - 14 November 2026")
  const formatPeriodDisplay = (startStr?: string, endStr?: string) => {
    if (!startStr || !endStr) return '';
    const parse = (str: string) => {
      const parts = str.split('-');
      if (parts.length === 3) {
        return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      }
      return new Date(str);
    };
    const fmt = (d: Date) =>
      d.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
      });
    const s = parse(startStr);
    const e = parse(endStr);
    if (startStr === endStr) {
      return `Reporting Period: ${fmt(s)}`;
    }
    return `Reporting Period: ${fmt(s)} - ${fmt(e)}`;
  };

  const totalSales = Number(salesData?.total_sales ?? 0);
  const totalExpenses = Number(expenseData?.total_expenses ?? 0);
  const netBalance = totalSales - totalExpenses;
  const reportingPeriodText = formatPeriodDisplay(salesData?.period_start, salesData?.period_end);

  return (
    <div className="space-y-6">
      {/* Title & Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Financial & Sales Reports
          </h2>
          <p className="text-xs text-zinc-500">
            Line-by-line sales transactions, operational expenses, and net balance summary.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          {/* Prominent PDF Download Button */}
          <button
            onClick={handleDownloadPdf}
            disabled={pdfDownloading || loading}
            className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-3.5 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95 disabled:opacity-50 transition-all"
            title="Download report in professional PDF format"
          >
            {pdfDownloading ? (
              <>
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-950 border-t-transparent" />
                <span>Generating PDF...</span>
              </>
            ) : (
              <>
                <Download className="h-3.5 w-3.5 text-zinc-950" />
                <span>Download Report (PDF)</span>
              </>
            )}
          </button>

          {/* Refresh Button */}
          <button
            onClick={() => loadReports(preset, startDate, endDate)}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50 disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Preset Filter Bar */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {[
              { id: 'today', label: 'Today' },
              { id: 'yesterday', label: 'Yesterday' },
              { id: 'this_week', label: 'This Week' },
              { id: 'this_month', label: 'This Month' },
              { id: 'previous_month', label: 'Previous Month' },
              { id: 'custom', label: 'Custom Date Range' },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => handlePresetChange(p.id)}
                className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all ${preset === p.id
                    ? 'bg-zinc-900 text-white shadow-sm'
                    : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'
                  }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {preset === 'custom' && (
            <form onSubmit={handleCustomSubmit} className="flex flex-wrap items-center gap-2">
              <input
                type="date"
                required
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="rounded-lg border border-zinc-300 px-2.5 py-1 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
              />
              <span className="text-xs text-zinc-400">to</span>
              <input
                type="date"
                required
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="rounded-lg border border-zinc-300 px-2.5 py-1 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
              />
              <button
                type="submit"
                disabled={loading}
                className="rounded-lg bg-amber-500 px-3 py-1 text-xs font-bold text-zinc-950 hover:bg-amber-400 active:scale-95 disabled:opacity-50"
              >
                Apply
              </button>
            </form>
          )}
        </div>

        {/* Validation Error Banner */}
        {validationError && (
          <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
            <span>{validationError}</span>
          </div>
        )}
      </div>

      {/* Displayed Reporting Period Banner */}
      {reportingPeriodText && (
        <div className="flex items-center gap-2 rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-2.5 text-xs font-bold text-zinc-800">
          <Calendar className="h-4 w-4 text-amber-600" />
          <span>{reportingPeriodText}</span>
        </div>
      )}

      {/* API Error Message Banner */}
      {errorMessage && (
        <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Loading Indicator */}
      {loading ? (
        <div className="flex h-64 flex-col items-center justify-center gap-2 rounded-2xl border border-zinc-200 bg-white p-8">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
          <p className="text-xs text-zinc-400">Loading sales & expense records...</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* SECTION 1: Sales Report */}
          <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-100 p-4 bg-zinc-50/50">
              <div className="flex items-center gap-2">
                <ShoppingBag className="h-4 w-4 text-amber-600" />
                <h3 className="text-sm font-bold text-zinc-900 font-serif">Sales Report</h3>
              </div>
              <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-semibold text-zinc-600">
                {salesData?.bills.length ?? 0} Completed Bills
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 bg-zinc-100/75 text-[11px] font-bold text-zinc-600 uppercase tracking-wider">
                    <th className="py-3 px-4">Bill No.</th>
                    <th className="py-3 px-4">Date & Time</th>
                    <th className="py-3 px-4 text-center">Items</th>
                    <th className="py-3 px-4">Payment Method</th>
                    <th className="py-3 px-4 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {salesData && salesData.bills.length > 0 ? (
                    salesData.bills.map((bill) => (
                      <tr key={bill.id} className="hover:bg-zinc-50/60 transition-colors">
                        <td className="py-3 px-4 font-mono font-bold text-zinc-900">
                          {bill.bill_number}
                        </td>
                        <td className="py-3 px-4 text-zinc-600">
                          {formatDateTime(bill.created_at)}
                        </td>
                        <td className="py-3 px-4 text-center font-semibold text-zinc-700">
                          {bill.items_count}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-bold ${bill.payment_method.includes('Split') ||
                                bill.payment_method.includes('+')
                                ? 'bg-purple-100 text-purple-800'
                                : bill.payment_method === 'UPI'
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-emerald-100 text-emerald-800'
                              }`}
                          >
                            {bill.payment_method}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right font-black text-zinc-900">
                          {formatCurrency(bill.total_amount)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-xs text-zinc-400 italic">
                        No sales recorded for this period.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Total Sales Summary Bar */}
            <div className="flex items-center justify-between border-t-2 border-zinc-900 bg-zinc-50 p-4">
              <span className="text-xs font-bold text-zinc-700 uppercase tracking-wider">
                Total Sales
              </span>
              <span className="text-base font-black text-zinc-950">
                {formatCurrency(totalSales)}
              </span>
            </div>
          </div>

          {/* SECTION 2: Expenses Report */}
          <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-100 p-4 bg-zinc-50/50">
              <div className="flex items-center gap-2">
                <Receipt className="h-4 w-4 text-amber-600" />
                <h3 className="text-sm font-bold text-zinc-900 font-serif">Expenses Report</h3>
              </div>
              <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-semibold text-zinc-600">
                {expenseData?.expenses.length ?? 0} Recorded Expenses
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 bg-zinc-100/75 text-[11px] font-bold text-zinc-600 uppercase tracking-wider">
                    <th className="py-3 px-4">Date & Time</th>
                    <th className="py-3 px-4">Expense Category</th>
                    <th className="py-3 px-4">Description</th>
                    <th className="py-3 px-4 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {expenseData && expenseData.expenses.length > 0 ? (
                    expenseData.expenses.map((exp) => (
                      <tr key={exp.id} className="hover:bg-zinc-50/60 transition-colors">
                        <td className="py-3 px-4 text-zinc-600">
                          {formatDateTime(exp.expense_date)}
                        </td>
                        <td className="py-3 px-4">
                          <span className="inline-flex items-center rounded-md bg-zinc-100 px-2 py-0.5 text-[11px] font-bold text-zinc-800">
                            {exp.category}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-zinc-600 max-w-xs truncate">
                          {exp.description || exp.expense_title || '—'}
                        </td>
                        <td className="py-3 px-4 text-right font-black text-rose-600">
                          {formatCurrency(exp.amount)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-xs text-zinc-400 italic">
                        No expenses recorded for this period.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Total Expenses Summary Bar */}
            <div className="flex items-center justify-between border-t-2 border-zinc-900 bg-zinc-50 p-4">
              <span className="text-xs font-bold text-zinc-700 uppercase tracking-wider">
                Total Expenses
              </span>
              <span className="text-base font-black text-rose-600">
                {formatCurrency(totalExpenses)}
              </span>
            </div>
          </div>

          {/* SECTION 3: Summary Cards (at the bottom) */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            {/* Card 1: Total Sales */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  Total Sales
                </span>
                <div className="rounded-lg bg-emerald-50 p-1.5 text-emerald-600">
                  <ArrowUpRight className="h-4 w-4" />
                </div>
              </div>
              <p className="text-2xl font-black text-zinc-900">
                {formatCurrency(totalSales)}
              </p>
              <p className="text-[11px] text-zinc-400">
                Sum of {salesData?.bills.length ?? 0} completed sales in period
              </p>
            </div>

            {/* Card 2: Total Expenses */}
            <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  Total Expenses
                </span>
                <div className="rounded-lg bg-rose-50 p-1.5 text-rose-600">
                  <ArrowDownRight className="h-4 w-4" />
                </div>
              </div>
              <p className="text-2xl font-black text-rose-600">
                {formatCurrency(totalExpenses)}
              </p>
              <p className="text-[11px] text-zinc-400">
                Sum of {expenseData?.expenses.length ?? 0} operational expenses in period
              </p>
            </div>

            {/* Card 3: Net Balance (Prominent) */}
            <div className="rounded-2xl border-2 border-amber-400 bg-amber-50/70 p-5 shadow-sm space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-amber-900 uppercase tracking-wider">
                  Net Balance
                </span>
                <div className="rounded-lg bg-amber-200/70 p-1.5 text-amber-800">
                  <Scale className="h-4 w-4" />
                </div>
              </div>
              <p
                className={`text-2xl font-black ${netBalance >= 0 ? 'text-zinc-950' : 'text-rose-700'
                  }`}
              >
                {formatCurrency(netBalance)}
              </p>
              <p className="text-[11px] font-semibold text-amber-800/80">
                Total Sales minus Total Expenses
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
