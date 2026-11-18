import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ShoppingCart,
  Receipt,
  Boxes,
  Search,
  CheckCircle2,
  Clock,
  Eye,
  Store,
} from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { Bill } from '../../types';
import { billingService } from '../../services/billingService';
import { formatCurrency, formatDateTime, getStatusBadgeClass } from '../../utils/formatters';
import { ThermalReceiptModal } from '../../components/receipts/ThermalReceiptModal';

export const StaffDashboardPage: React.FC = () => {
  const { user } = useAuthStore();
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBillForReceipt, setSelectedBillForReceipt] = useState<string | null>(null);

  useEffect(() => {
    loadStaffBills();
  }, []);

  const loadStaffBills = async () => {
    setLoading(true);
    try {
      const res = await billingService.getBills({ page: 1, page_size: 10 });
      setBills(res.items || []);
    } catch (err) {
      console.error('Failed to load bills', err);
    } finally {
      setLoading(false);
    }
  };

  const todayBills = bills.filter(
    (b) => new Date(b.bill_date).toDateString() === new Date().toDateString()
  );
  const todayTotal = todayBills.reduce(
    (acc, b) => acc + (b.payment_status === 'PAID' ? Number(b.total_amount) : 0),
    0
  );

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-3xl border border-zinc-200 bg-gradient-to-r from-zinc-900 to-zinc-800 p-6 sm:p-8 text-white shadow-lg">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="rounded bg-amber-400/20 px-2 py-0.5 text-[11px] font-bold text-amber-300 uppercase tracking-wider">
                Active Cashier Session
              </span>
              <span className="text-xs text-zinc-400">
                Staff ID: {user?.employee_id || user?.username}
              </span>
            </div>
            <h2 className="text-2xl font-serif font-black tracking-wide text-white">
              Welcome, {user?.full_name}
            </h2>
            <p className="mt-1 text-xs text-zinc-400 max-w-xl">
              VIYON Sathyamangalam Store Terminal. Start customer checkout, verify pending UPI, or search product inventory below.
            </p>
          </div>

          <Link
            to="/pos"
            className="flex items-center justify-center gap-2 rounded-2xl bg-amber-500 px-6 py-3.5 text-sm font-bold text-zinc-950 shadow-md hover:bg-amber-400 active:scale-95 transition-all"
          >
            <ShoppingCart className="h-5 w-5" />
            <span>Open POS Checkout</span>
          </Link>
        </div>
      </div>

      {/* Quick Action Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Link
          to="/pos"
          className="group rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm transition-all hover:border-amber-500 hover:shadow-md flex items-center gap-4"
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 text-amber-600 group-hover:scale-105 transition-transform">
            <ShoppingCart className="h-6 w-6" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-zinc-900">New Bill</h4>
            <p className="text-xs text-zinc-500">Scan barcodes and take payment</p>
          </div>
        </Link>

        <Link
          to="/products"
          className="group rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm transition-all hover:border-amber-500 hover:shadow-md flex items-center gap-4"
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-600 group-hover:scale-105 transition-transform">
            <Search className="h-6 w-6" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-zinc-900">Search Products</h4>
            <p className="text-xs text-zinc-500">Check style codes and sizes</p>
          </div>
        </Link>

        <Link
          to="/inventory"
          className="group rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm transition-all hover:border-amber-500 hover:shadow-md flex items-center gap-4"
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 group-hover:scale-105 transition-transform">
            <Boxes className="h-6 w-6" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-zinc-900">Check Stock</h4>
            <p className="text-xs text-zinc-500">View real-time item quantities</p>
          </div>
        </Link>
      </div>

      {/* Recent Bills Counter Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-zinc-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Receipt className="h-4 w-4 text-amber-500" />
            <h3 className="text-sm font-bold text-zinc-900">Recent Counter Bills</h3>
          </div>
          <Link to="/bills" className="text-xs font-semibold text-amber-600 hover:text-amber-700">
            View all history &rarr;
          </Link>
        </div>

        {loading ? (
          <div className="flex h-40 flex-col items-center justify-center gap-2">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading bills...</p>
          </div>
        ) : bills.length === 0 ? (
          <p className="py-8 text-center text-xs text-zinc-400">No bills generated yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-100">
                <tr>
                  <th className="py-2.5 px-3">Bill Number</th>
                  <th className="py-2.5 px-3">Date & Time</th>
                  <th className="py-2.5 px-3">Items</th>
                  <th className="py-2.5 px-3">Total Amount</th>
                  <th className="py-2.5 px-3">Payment Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {bills.map((b) => (
                  <tr key={b.id} className="hover:bg-zinc-50/50">
                    <td className="py-2.5 px-3 font-bold text-zinc-900">{b.bill_number}</td>
                    <td className="py-2.5 px-3 text-zinc-500">{formatDateTime(b.bill_date)}</td>
                    <td className="py-2.5 px-3 text-zinc-600">{b.items?.length || 0} items</td>
                    <td className="py-2.5 px-3 font-bold text-zinc-900">
                      {formatCurrency(b.total_amount)}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getStatusBadgeClass(b.payment_status)}`}>
                        {b.payment_status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => setSelectedBillForReceipt(b.id)}
                        className="rounded-lg bg-zinc-100 px-2.5 py-1 text-[11px] font-semibold text-zinc-700 hover:bg-zinc-200"
                      >
                        Reprint Receipt
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Receipt Modal */}
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
