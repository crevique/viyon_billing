import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  CreditCard,
  Smartphone,
  AlertTriangle,
  Receipt,
  Boxes,
  Truck,
  Wallet,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  ShoppingCart,
  Eye,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  Bill,
  FinancialOverview,
  InventoryItem,
  InventorySummary,
  PurchaseSummary,
  StockMovement,
  Expense,
} from '../../types';
import { financeService } from '../../services/financeService';
import { billingService } from '../../services/billingService';
import { inventoryService } from '../../services/inventoryService';
import { purchaseService } from '../../services/purchaseService';
import { formatCurrency, formatDateTime, getStatusBadgeClass } from '../../utils/formatters';
import { ThermalReceiptModal } from '../../components/receipts/ThermalReceiptModal';

export const OverviewPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [finance, setFinance] = useState<FinancialOverview | null>(null);
  const [invSummary, setInvSummary] = useState<InventorySummary | null>(null);
  const [purchaseSummary, setPurchaseSummary] = useState<PurchaseSummary | null>(null);
  const [recentBills, setRecentBills] = useState<Bill[]>([]);
  const [lowStockItems, setLowStockItems] = useState<InventoryItem[]>([]);
  const [recentMovements, setRecentMovements] = useState<StockMovement[]>([]);
  const [recentExpenses, setRecentExpenses] = useState<Expense[]>([]);
  const [selectedBillForReceipt, setSelectedBillForReceipt] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [
        finData,
        billsData,
        invSumData,
        lowStockData,
        movData,
        poSumData,
        expData,
      ] = await Promise.allSettled([
        financeService.getOverview({ preset: 'today' }),
        billingService.getBills({ page: 1, page_size: 5 }),
        inventoryService.getSummary(),
        inventoryService.getLowStock({ limit: 5 }),
        inventoryService.getMovements({ limit: 5 }),
        purchaseService.getSummary(),
        financeService.getExpenses({ page: 1, page_size: 5 }),
      ]);

      if (finData.status === 'fulfilled') setFinance(finData.value);
      if (billsData.status === 'fulfilled') setRecentBills(billsData.value.items || []);
      if (invSumData.status === 'fulfilled') setInvSummary(invSumData.value);
      if (lowStockData.status === 'fulfilled') setLowStockItems(lowStockData.value.items || []);
      if (movData.status === 'fulfilled') setRecentMovements(movData.value.items || []);
      if (poSumData.status === 'fulfilled') setPurchaseSummary(poSumData.value);
      if (expData.status === 'fulfilled') setRecentExpenses(expData.value.items || []);
    } catch (err) {
      console.error('Error fetching dashboard overview', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Refresh */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Store Executive Overview
          </h2>
          <p className="text-xs text-zinc-500">
            Real-time financial performance, inventory levels, and counter collections for today.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchDashboardData}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <Link
            to="/pos"
            className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-3.5 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95"
          >
            <ShoppingCart className="h-4 w-4" />
            <span>Launch POS</span>
          </Link>
        </div>
      </div>

      {/* Primary Financial Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Net Sales */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-500">Today's Net Sales</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <TrendingUp className="h-4 w-4" />
            </div>
          </div>
          <p className="mt-2 text-2xl font-black text-zinc-900">
            {formatCurrency(finance?.net_sales)}
          </p>
          <div className="mt-2 flex items-center gap-2 text-xs text-zinc-500">
            <span>Completed bills: {finance?.completed_bills_count || 0}</span>
            {Number(finance?.cancelled_bills_count || 0) > 0 && (
              <span className="text-rose-600">
                ({finance?.cancelled_bills_count} cancelled)
              </span>
            )}
          </div>
        </div>

        {/* Confirmed Cash */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-500">Cash Collections</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <CreditCard className="h-4 w-4" />
            </div>
          </div>
          <p className="mt-2 text-2xl font-black text-emerald-600">
            {formatCurrency(finance?.cash_collections)}
          </p>
          <p className="mt-2 text-xs text-zinc-400">Physical cash confirmed at counter</p>
        </div>

        {/* Confirmed UPI */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-500">Confirmed UPI</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Smartphone className="h-4 w-4" />
            </div>
          </div>
          <p className="mt-2 text-2xl font-black text-blue-600">
            {formatCurrency(finance?.upi_collections)}
          </p>
          <p className="mt-2 text-xs text-zinc-400">Verified received in bank</p>
        </div>

        {/* Pending UPI Payments */}
        <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-900">Pending UPI</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
              <AlertTriangle className="h-4 w-4" />
            </div>
          </div>
          <p className="mt-2 text-2xl font-black text-amber-700">
            {formatCurrency(finance?.pending_upi_amount)}
          </p>
          <p className="mt-2 text-xs text-amber-800/80">Requires manual cashier verification</p>
        </div>
      </div>

      {/* Operational Highlights Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Inventory Units */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-100 text-zinc-700">
            <Boxes className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-zinc-500">Total Stock in Store</p>
            <p className="text-lg font-bold text-zinc-900">
              {invSummary?.total_stock?.toLocaleString() || 0} Units
            </p>
          </div>
        </div>

        {/* Low Stock Alerts */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-zinc-500">Low Stock SKUs</p>
            <p className="text-lg font-bold text-rose-600">
              {invSummary?.low_stock_items || 0} Items
            </p>
          </div>
        </div>

        {/* Total Operating Expenses */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
            <Wallet className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-zinc-500">Today's Expenses</p>
            <p className="text-lg font-bold text-zinc-900">
              {formatCurrency(finance?.total_operating_expenses)}
            </p>
          </div>
        </div>

        {/* Supplier Liabilities */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
            <Truck className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-zinc-500">Supplier Outstanding</p>
            <p className="text-lg font-bold text-zinc-900">
              {formatCurrency(purchaseSummary?.total_supplier_outstanding)}
            </p>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Recent Transactions & Low Stock Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Counter Bills */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-zinc-100 pb-3 mb-3">
            <div className="flex items-center gap-2">
              <Receipt className="h-4 w-4 text-amber-500" />
              <h3 className="text-sm font-bold text-zinc-900">Recent Sales Bills</h3>
            </div>
            <Link to="/bills" className="text-xs font-semibold text-amber-600 hover:text-amber-700">
              View all &rarr;
            </Link>
          </div>

          {recentBills.length === 0 ? (
            <p className="py-6 text-center text-xs text-zinc-400">No bills generated today yet.</p>
          ) : (
            <div className="divide-y divide-zinc-100">
              {recentBills.map((b) => (
                <div key={b.id} className="py-2.5 flex items-center justify-between text-xs">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-zinc-900">{b.bill_number}</span>
                      <span className={`rounded border px-1.5 py-0.2 text-[10px] font-semibold ${getStatusBadgeClass(b.payment_status)}`}>
                        {b.payment_status}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 mt-0.5">
                      {formatDateTime(b.bill_date)} • Cashier: {b.staff_name || 'Staff'}
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="font-bold text-zinc-900">
                      {formatCurrency(b.total_amount)}
                    </span>
                    <button
                      onClick={() => setSelectedBillForReceipt(b.id)}
                      className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
                      title="View Receipt"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Low Stock Alerts */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-zinc-100 pb-3 mb-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-500" />
              <h3 className="text-sm font-bold text-zinc-900">Low Stock Urgent Alerts</h3>
            </div>
            <Link to="/inventory" className="text-xs font-semibold text-amber-600 hover:text-amber-700">
              Manage inventory &rarr;
            </Link>
          </div>

          {lowStockItems.length === 0 ? (
            <p className="py-6 text-center text-xs text-emerald-600 font-medium">
              ✓ All inventory items are comfortably above threshold!
            </p>
          ) : (
            <div className="divide-y divide-zinc-100">
              {lowStockItems.map((item) => (
                <div key={item.id} className="py-2.5 flex items-center justify-between text-xs">
                  <div>
                    <p className="font-bold text-zinc-900">{item.product_name}</p>
                    <p className="text-[11px] text-zinc-400 mt-0.5 font-mono">
                      {item.size ? `Size: ${item.size} • ` : ''}SKU: {item.sku}
                    </p>
                  </div>

                  <div className="text-right">
                    <span className="rounded bg-rose-50 border border-rose-200 px-2 py-0.5 text-xs font-bold text-rose-700">
                      {item.quantity} left
                    </span>
                    <p className="text-[10px] text-zinc-400 mt-0.5">
                      Threshold: {item.low_stock_threshold}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Stock Movements and Recent Expenses */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Stock Movements */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-zinc-100 pb-3 mb-3">
            <h3 className="text-sm font-bold text-zinc-900">Recent Stock Ledger Entries</h3>
            <Link to="/inventory/movements" className="text-xs font-semibold text-amber-600 hover:text-amber-700">
              View ledger &rarr;
            </Link>
          </div>

          {recentMovements.length === 0 ? (
            <p className="py-6 text-center text-xs text-zinc-400">No stock movements logged today.</p>
          ) : (
            <div className="divide-y divide-zinc-100">
              {recentMovements.map((m) => (
                <div key={m.id} className="py-2.5 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-semibold text-zinc-800">{m.product_name}</span>
                    <p className="text-[11px] text-zinc-400">
                      {m.movement_type} • By: {m.created_by_user_name || 'System'}
                    </p>
                  </div>
                  <span
                    className={`font-bold ${
                      m.quantity_change > 0 ? 'text-emerald-600' : 'text-rose-600'
                    }`}
                  >
                    {m.quantity_change > 0 ? `+${m.quantity_change}` : m.quantity_change}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Expenses */}
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-zinc-100 pb-3 mb-3">
            <h3 className="text-sm font-bold text-zinc-900">Recent Store Expenses</h3>
            <Link to="/expenses" className="text-xs font-semibold text-amber-600 hover:text-amber-700">
              Expenses ledger &rarr;
            </Link>
          </div>

          {recentExpenses.length === 0 ? (
            <p className="py-6 text-center text-xs text-zinc-400">No expenses recorded today.</p>
          ) : (
            <div className="divide-y divide-zinc-100">
              {recentExpenses.map((exp) => (
                <div key={exp.id} className="py-2.5 flex items-center justify-between text-xs">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-zinc-800">{exp.expense_title}</span>
                      <span className="rounded bg-zinc-100 px-1.5 py-0.2 text-[10px] text-zinc-600">
                        {exp.category}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400">
                      {formatDateTime(exp.expense_date)} • {exp.payment_method}
                    </p>
                  </div>
                  <span className="font-bold text-rose-600">
                    -{formatCurrency(exp.amount)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Thermal Receipt Preview Modal */}
      {selectedBillForReceipt && (
        <ThermalReceiptModal
          billId={selectedBillForReceipt}
          onClose={() => setSelectedBillForReceipt(null)}
          isReprint={true}
        />
      )}
    </div>
  );
};
