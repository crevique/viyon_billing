import React from 'react';
import { ProfitLossReport, formatINR } from './types';

interface ProfitLossCardProps {
  report: ProfitLossReport;
}

export const ProfitLossCard: React.FC<ProfitLossCardProps> = ({ report }) => {
  const getBadge = () => {
    switch (report.profit_status) {
      case 'AVAILABLE':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            Verified Purchase Cost
          </span>
        );
      case 'PARTIAL':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
            Partial (Estimated)
          </span>
        );
      case 'UNAVAILABLE':
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
            Cost Data Unavailable
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between pb-4 border-b border-gray-100">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Profit & Loss Analysis</h3>
          <p className="text-xs text-gray-500 mt-0.5">Based on catalogue purchase cost data</p>
        </div>
        <div>{getBadge()}</div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
        <div className="bg-gray-50 rounded-lg p-4">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Revenue (Net Sales)</span>
          <p className="text-xl font-bold text-gray-900 mt-1">{formatINR(report.revenue)}</p>
        </div>

        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex justify-between items-center">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Cost of Goods (COGS)</span>
            <span className="text-xs text-gray-400">
              {report.items_with_cost_count}/{report.items_sold_count} items
            </span>
          </div>
          <p className="text-xl font-bold text-gray-900 mt-1">
            {report.cogs !== null && report.cogs !== undefined ? formatINR(report.cogs) : 'N/A'}
          </p>
        </div>

        <div className="bg-gray-50 rounded-lg p-4">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Operating Expenses</span>
          <p className="text-xl font-bold text-red-600 mt-1">{formatINR(report.operating_expenses)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        <div className="border border-gray-200 rounded-lg p-4 bg-emerald-50/40">
          <div className="flex justify-between items-baseline">
            <span className="text-sm font-semibold text-gray-700">Gross Profit</span>
            {report.gross_profit_margin_pct && (
              <span className="text-xs font-medium text-emerald-700">{report.gross_profit_margin_pct}% margin</span>
            )}
          </div>
          <p className="text-2xl font-black text-emerald-800 mt-2">
            {report.gross_profit !== null && report.gross_profit !== undefined
              ? formatINR(report.gross_profit)
              : 'Unavailable'}
          </p>
        </div>

        <div className="border border-gray-200 rounded-lg p-4 bg-blue-50/40">
          <div className="flex justify-between items-baseline">
            <span className="text-sm font-semibold text-gray-700">Net Operating Profit</span>
            {report.net_profit_margin_pct && (
              <span className="text-xs font-medium text-blue-700">{report.net_profit_margin_pct}% margin</span>
            )}
          </div>
          <p className="text-2xl font-black text-blue-900 mt-2">
            {report.net_operating_profit !== null && report.net_operating_profit !== undefined
              ? formatINR(report.net_operating_profit)
              : 'Unavailable'}
          </p>
        </div>
      </div>

      {report.explanation_note && (
        <div className="mt-4 p-3 bg-amber-50/60 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start space-x-2">
          <svg className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{report.explanation_note}</span>
        </div>
      )}
    </div>
  );
};
