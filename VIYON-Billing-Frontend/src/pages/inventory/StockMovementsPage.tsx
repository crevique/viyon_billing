import React, { useState, useEffect } from 'react';
import { History, Search, Filter, RefreshCw, ArrowUpRight, ArrowDownRight, Trash2, X, AlertTriangle } from 'lucide-react';
import { StockMovement } from '../../types';
import { inventoryService } from '../../services/inventoryService';
import { useAuthStore } from '../../stores/useAuthStore';
import { formatDateTime } from '../../utils/formatters';

export const StockMovementsPage: React.FC = () => {
  const { role } = useAuthStore();
  const isOwner = role === 'OWNER' || role === 'ADMIN';

  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [movementType, setMovementType] = useState('');
  const [total, setTotal] = useState(0);

  // Deletion modal state
  const [selectedMovementForDelete, setSelectedMovementForDelete] = useState<StockMovement | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  useEffect(() => {
    loadLedger();
  }, [movementType]);

  const loadLedger = async () => {
    setLoading(true);
    try {
      const res = await inventoryService.getMovements({
        movement_type: movementType || undefined,
        limit: 100,
      });
      setMovements(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error('Failed to load stock movements', err);
    } finally {
      setLoading(false);
    }
  };

  const getMovementBadge = (type: string) => {
    switch (type) {
      case 'PURCHASE':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'SALE':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'ADJUSTMENT':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'CANCELLATION':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      default:
        return 'bg-zinc-100 text-zinc-700 border-zinc-200';
    }
  };

  const handleDeleteMovement = async () => {
    if (!selectedMovementForDelete || isDeleting) return;

    setIsDeleting(true);
    try {
      const res = await inventoryService.deleteStockMovement(selectedMovementForDelete.id);
      setNotification({
        type: 'success',
        message: res.message || 'Stock movement deleted and inventory reversed successfully.',
      });
      setSelectedMovementForDelete(null);
      await loadLedger();
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to delete stock movement.';
      setNotification({
        type: 'error',
        message: errMsg,
      });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Notification Banner */}
      {notification && (
        <div
          className={`flex items-center justify-between rounded-xl p-3 text-xs font-semibold ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          <span>{notification.message}</span>
          <button
            onClick={() => setNotification(null)}
            className="text-zinc-400 hover:text-zinc-600 p-0.5"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Stock Movement Ledger
          </h2>
          <p className="text-xs text-zinc-500">
            Immutable audit trail of all inventory modifications (Purchases, POS Sales, Adjustments, Bill Cancellations).
          </p>
        </div>

        <button
          onClick={loadLedger}
          className="flex items-center gap-1.5 self-start sm:self-auto rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter Bar */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <Filter className="h-4 w-4 text-zinc-400" />
          <select
            value={movementType}
            onChange={(e) => setMovementType(e.target.value)}
            className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-700 focus:border-amber-500 focus:outline-none"
          >
            <option value="">Movement Type: All</option>
            <option value="PURCHASE">PURCHASE (Inward Delivery)</option>
            <option value="SALE">SALE (Counter POS Checkout)</option>
            <option value="ADJUSTMENT">ADJUSTMENT (Audit Correction)</option>
            <option value="CANCELLATION">CANCELLATION (Restored Stock)</option>
          </select>
          <span className="text-xs text-zinc-400 ml-auto">{total} entries recorded</span>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading audit ledger...</p>
          </div>
        ) : movements.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            No stock movements found for the selected filter.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">Date & Time</th>
                  <th className="py-3 px-4">Product Details</th>
                  <th className="py-3 px-4">SKU</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4 text-right">Qty Change</th>
                  <th className="py-3 px-4">Audit Reason / Ref</th>
                  <th className="py-3 px-4">Logged By</th>
                  {isOwner && <th className="py-3 px-4 text-center">Action</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {movements.map((m) => (
                  <tr key={m.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 text-zinc-500">{formatDateTime(m.created_at)}</td>
                    <td className="py-3 px-4 font-bold text-zinc-900">
                      <div>
                        <span>{m.product_name}</span>
                        {m.variant_size && (
                          <span className="ml-1.5 font-normal text-zinc-500 text-[11px]">
                            (Size: {m.variant_size})
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-zinc-400">{m.sku || '—'}</td>
                    <td className="py-3 px-4">
                      <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getMovementBadge(m.movement_type)}`}>
                        {m.movement_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-black">
                      <span
                        className={`inline-flex items-center gap-0.5 ${
                          m.quantity_change > 0 ? 'text-emerald-600' : 'text-rose-600'
                        }`}
                      >
                        {m.quantity_change > 0 ? (
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        ) : (
                          <ArrowDownRight className="h-3.5 w-3.5" />
                        )}
                        {m.quantity_change > 0 ? `+${m.quantity_change}` : m.quantity_change}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-zinc-600 max-w-xs truncate">
                      {m.notes || m.reference_type || '—'}
                    </td>
                    <td className="py-3 px-4 text-zinc-500">
                      {m.created_by_user_name || 'System'}
                    </td>
                    {isOwner && (
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => setSelectedMovementForDelete(m)}
                          className="rounded-lg bg-rose-50 border border-rose-200 p-1 text-[11px] font-semibold text-rose-700 hover:bg-rose-100"
                          title="Delete Stock Movement"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete Stock Movement Confirmation Modal */}
      {selectedMovementForDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center gap-3 border-b border-zinc-100 pb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
                <Trash2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-zinc-900">Delete Stock Movement</h3>
                <p className="text-xs text-zinc-500">Confirm audit ledger reversal</p>
              </div>
            </div>

            <div className="my-4 space-y-3">
              <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Movement Type:</span>
                  <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getMovementBadge(selectedMovementForDelete.movement_type)}`}>
                    {selectedMovementForDelete.movement_type}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Product:</span>
                  <span className="font-bold text-zinc-900">{selectedMovementForDelete.product_name}</span>
                </div>
                {selectedMovementForDelete.variant_size && (
                  <div className="flex justify-between">
                    <span className="text-zinc-500 font-medium">Size:</span>
                    <span className="font-semibold text-zinc-800">{selectedMovementForDelete.variant_size}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Original Quantity Change:</span>
                  <span className={`font-black text-sm ${selectedMovementForDelete.quantity_change > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                    {selectedMovementForDelete.quantity_change > 0 ? `+${selectedMovementForDelete.quantity_change}` : selectedMovementForDelete.quantity_change}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Date:</span>
                  <span className="text-zinc-700">{formatDateTime(selectedMovementForDelete.created_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Reference:</span>
                  <span className="text-zinc-700">{selectedMovementForDelete.notes || selectedMovementForDelete.reference_type || '—'}</span>
                </div>
              </div>

              {/* Guard checks */}
              {selectedMovementForDelete.reference_type === 'BILL' || selectedMovementForDelete.movement_type === 'SALE' ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50/90 p-3 text-xs text-rose-800 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
                  <p>
                    <strong>Blocked:</strong> This movement was generated by an active sales bill. Sales ledger movements
                    cannot be deleted directly. Please use the <strong>Bills &amp; Transactions &rarr; Cancel Bill</strong> workflow
                    to safely void the transaction and return items to inventory.
                  </p>
                </div>
              ) : selectedMovementForDelete.reference_type === 'GOODS_RECEIPT' ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50/90 p-3 text-xs text-amber-800 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
                  <p>
                    <strong>Blocked:</strong> This movement is linked to a Goods Receipt inward. Please manage goods receipt adjustments through the Purchase Order workflow.
                  </p>
                </div>
              ) : (
                <div className="rounded-xl border border-blue-200 bg-blue-50/80 p-3 text-xs text-blue-800 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-blue-600 mt-0.5" />
                  <p>
                    <strong>Stock Reversal Impact:</strong> Deleting this record will automatically apply a{' '}
                    <strong>{-selectedMovementForDelete.quantity_change > 0 ? `+${-selectedMovementForDelete.quantity_change}` : -selectedMovementForDelete.quantity_change}</strong>{' '}
                    unit adjustment to current inventory to keep stock counts perfectly consistent.
                  </p>
                </div>
              )}
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setSelectedMovementForDelete(null)}
                disabled={isDeleting}
                className="flex-1 rounded-xl border border-zinc-300 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              >
                Cancel
              </button>
              {!(selectedMovementForDelete.reference_type === 'BILL' || selectedMovementForDelete.movement_type === 'SALE' || selectedMovementForDelete.reference_type === 'GOODS_RECEIPT') && (
                <button
                  type="button"
                  onClick={handleDeleteMovement}
                  disabled={isDeleting}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-rose-600 py-2.5 text-xs font-bold text-white shadow-md hover:bg-rose-500 disabled:opacity-50 transition-all"
                >
                  {isDeleting ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      <span>Reversing...</span>
                    </>
                  ) : (
                    <span>Confirm Delete &amp; Reverse</span>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
