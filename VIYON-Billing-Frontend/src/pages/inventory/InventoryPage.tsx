import React, { useState, useEffect } from 'react';
import {
  Boxes,
  AlertTriangle,
  ArrowDownLeft,
  SlidersHorizontal,
  Search,
  Plus,
  RefreshCw,
  X,
  CheckCircle,
  Trash2,
} from 'lucide-react';
import { InventoryItem, InventorySummary } from '../../types';
import { inventoryService } from '../../services/inventoryService';
import { useAuthStore } from '../../stores/useAuthStore';
import { getStatusBadgeClass } from '../../utils/formatters';

export const InventoryPage: React.FC = () => {
  const { role } = useAuthStore();
  const isOwner = role === 'OWNER' || role === 'ADMIN';

  const [items, setItems] = useState<InventoryItem[]>([]);
  const [summary, setSummary] = useState<InventorySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stockStatus, setStockStatus] = useState('');

  // Modals
  const [isInwardModalOpen, setIsInwardModalOpen] = useState(false);
  const [isAdjustModalOpen, setIsAdjustModalOpen] = useState(false);
  const [selectedItemForAction, setSelectedItemForAction] = useState<InventoryItem | null>(null);

  // Inward form
  const [inwardQty, setInwardQty] = useState('');
  const [inwardSupplier, setInwardSupplier] = useState('');
  const [inwardRef, setInwardRef] = useState('');
  const [inwardNotes, setInwardNotes] = useState('');

  // Adjust form
  const [adjustQtyChange, setAdjustQtyChange] = useState('');
  const [adjustReason, setAdjustReason] = useState('');
  const [adjustType, setAdjustType] = useState<'ADJUSTMENT' | 'PURCHASE'>('ADJUSTMENT');

  // Delete modal
  const [itemToDelete, setItemToDelete] = useState<InventoryItem | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  const handleDeleteSubmit = async () => {
    if (!itemToDelete || isDeleting) return;

    setIsDeleting(true);
    try {
      const res = await inventoryService.deleteInventory(itemToDelete.id);
      setNotification({
        type: 'success',
        message: res.message || 'Inventory record deleted successfully.',
      });
      setIsDeleteModalOpen(false);
      setItemToDelete(null);
      await loadInventoryData();
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to delete inventory record.';
      setNotification({
        type: 'error',
        message: errMsg,
      });
    } finally {
      setIsDeleting(false);
    }
  };

  useEffect(() => {
    loadInventoryData();
  }, [stockStatus]);

  const loadInventoryData = async () => {
    setLoading(true);
    try {
      const [invData, sumData] = await Promise.all([
        inventoryService.getInventory({
          stock_status: stockStatus || undefined,
          search: search.trim() || undefined,
          page_size: 100,
        }),
        inventoryService.getSummary(),
      ]);
      setItems(invData.items || []);
      setSummary(sumData);
    } catch (err) {
      console.error('Failed to load inventory', err);
    } finally {
      setLoading(false);
    }
  };

  const handleInwardSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItemForAction) return;

    const qty = parseInt(inwardQty);
    if (!qty || qty <= 0) {
      alert('Please enter a valid positive quantity.');
      return;
    }

    setIsSubmitting(true);
    try {
      await inventoryService.inwardStock({
        product_id: selectedItemForAction.product_id,
        variant_id: selectedItemForAction.variant_id || null,
        quantity: qty,
        supplier_name: inwardSupplier.trim() || undefined,
        purchase_reference: inwardRef.trim() || undefined,
        notes: inwardNotes.trim() || undefined,
      });

      alert('Stock inward recorded successfully.');
      setIsInwardModalOpen(false);
      setSelectedItemForAction(null);
      setInwardQty('');
      setInwardSupplier('');
      setInwardRef('');
      setInwardNotes('');
      loadInventoryData();
    } catch (err: any) {
      alert(`Inward failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAdjustSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItemForAction) return;

    const change = parseInt(adjustQtyChange);
    if (!change || change === 0) {
      alert('Quantity change cannot be zero.');
      return;
    }
    if (!adjustReason.trim()) {
      alert('A reason is mandatory for stock adjustment audits.');
      return;
    }

    setIsSubmitting(true);
    try {
      await inventoryService.adjustStock({
        product_id: selectedItemForAction.product_id,
        variant_id: selectedItemForAction.variant_id || null,
        quantity_change: change,
        movement_type: adjustType,
        reason: adjustReason.trim(),
      });

      alert('Stock adjustment recorded successfully.');
      setIsAdjustModalOpen(false);
      setSelectedItemForAction(null);
      setAdjustQtyChange('');
      setAdjustReason('');
      loadInventoryData();
    } catch (err: any) {
      alert(`Adjustment failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredItems = items.filter((i) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      i.product_name.toLowerCase().includes(s) ||
      (i.sku && i.sku.toLowerCase().includes(s)) ||
      (i.barcode && i.barcode.toLowerCase().includes(s)) ||
      (i.product_code && i.product_code.toLowerCase().includes(s))
    );
  });

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
            Store Inventory Management
          </h2>
          <p className="text-xs text-zinc-500">
            Real-time physical stock counts, inward receiving, low-stock threshold triggers, and audit corrections.
          </p>
        </div>

        <button
          onClick={loadInventoryData}
          className="flex items-center gap-1.5 self-start sm:self-auto rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Summary Statistics */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div className="rounded-xl border border-zinc-200 bg-white p-3.5 shadow-sm">
            <span className="text-[11px] font-semibold text-zinc-400">Total Products</span>
            <p className="text-xl font-bold text-zinc-900 mt-1">{summary.total_products}</p>
          </div>
          <div className="rounded-xl border border-zinc-200 bg-white p-3.5 shadow-sm">
            <span className="text-[11px] font-semibold text-zinc-400">Total Variants</span>
            <p className="text-xl font-bold text-zinc-900 mt-1">{summary.total_variants}</p>
          </div>
          <div className="rounded-xl border border-zinc-200 bg-white p-3.5 shadow-sm">
            <span className="text-[11px] font-semibold text-zinc-400">Total Store Stock</span>
            <p className="text-xl font-bold text-zinc-900 mt-1">{summary.total_stock?.toLocaleString()} pcs</p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3.5 shadow-sm">
            <span className="text-[11px] font-semibold text-amber-800">Low Stock SKUs</span>
            <p className="text-xl font-bold text-amber-700 mt-1">{summary.low_stock_items}</p>
          </div>
          <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-3.5 shadow-sm">
            <span className="text-[11px] font-semibold text-rose-800">Out of Stock</span>
            <p className="text-xl font-bold text-rose-600 mt-1">{summary.out_of_stock_items}</p>
          </div>
        </div>
      )}

      {/* Filter and Search */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              placeholder="Search by product name, SKU, or barcode..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-zinc-200 bg-zinc-50 pl-9 pr-4 py-2 text-xs focus:border-amber-500 focus:bg-white focus:outline-none"
            />
          </div>

          <select
            value={stockStatus}
            onChange={(e) => setStockStatus(e.target.value)}
            className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-700 focus:border-amber-500 focus:outline-none"
          >
            <option value="">Status: All Levels</option>
            <option value="IN_STOCK">In Stock</option>
            <option value="LOW_STOCK">Low Stock</option>
            <option value="OUT_OF_STOCK">Out of Stock</option>
          </select>
        </div>
      </div>

      {/* Inventory Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading inventory levels...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            No inventory records matching your query.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">Item & Variation</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">SKU / Barcode</th>
                  <th className="py-3 px-4 text-right">Available Qty</th>
                  <th className="py-3 px-4 text-right">Threshold</th>
                  <th className="py-3 px-4">Status</th>
                  {isOwner && <th className="py-3 px-4 text-center">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {filteredItems.map((item) => (
                  <tr key={item.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-zinc-900">
                      <div>
                        <span>{item.product_name}</span>
                        {(item.size || item.color) && (
                          <p className="text-[11px] font-semibold text-zinc-500 font-sans">
                            {item.size ? `Size: ${item.size}` : ''}
                            {item.color ? ` • Color: ${item.color}` : ''}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-zinc-600">{item.category_name || '—'}</td>
                    <td className="py-3 px-4 font-mono text-zinc-400">{item.sku || '—'}</td>
                    <td className="py-3 px-4 text-right font-black text-sm text-zinc-900">
                      {item.quantity}
                    </td>
                    <td className="py-3 px-4 text-right text-zinc-500 font-medium">
                      {item.low_stock_threshold}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getStatusBadgeClass(item.stock_status)}`}>
                        {item.stock_status}
                      </span>
                    </td>
                    {isOwner && (
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            onClick={() => {
                              setSelectedItemForAction(item);
                              setIsInwardModalOpen(true);
                            }}
                            className="rounded-lg bg-emerald-50 border border-emerald-200 px-2 py-1 text-[11px] font-semibold text-emerald-700 hover:bg-emerald-100"
                            title="Stock Inward (Receive delivery)"
                          >
                            + Inward
                          </button>
                          <button
                            onClick={() => {
                              setSelectedItemForAction(item);
                              setIsAdjustModalOpen(true);
                            }}
                            className="rounded-lg bg-zinc-100 border border-zinc-200 px-2 py-1 text-[11px] font-semibold text-zinc-700 hover:bg-zinc-200"
                            title="Adjust / Audit Stock"
                          >
                            Adjust
                          </button>
                          <button
                            onClick={() => {
                              setItemToDelete(item);
                              setIsDeleteModalOpen(true);
                            }}
                            className="rounded-lg bg-rose-50 border border-rose-200 p-1 text-[11px] font-semibold text-rose-700 hover:bg-rose-100"
                            title="Delete Inventory Record"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Stock Inward Modal */}
      {isInwardModalOpen && selectedItemForAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-zinc-900">Stock Inward</h3>
                <p className="text-xs text-zinc-500">{selectedItemForAction.product_name}</p>
              </div>
              <button
                onClick={() => setIsInwardModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleInwardSubmit} className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Quantity Received *
                </label>
                <input
                  type="number"
                  min="1"
                  required
                  placeholder="e.g. 25"
                  value={inwardQty}
                  onChange={(e) => setInwardQty(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs font-semibold focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Supplier / Vendor Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Classic Textiles Tirupur"
                  value={inwardSupplier}
                  onChange={(e) => setInwardSupplier(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Invoice / PO Reference
                </label>
                <input
                  type="text"
                  placeholder="e.g. INV-9042"
                  value={inwardRef}
                  onChange={(e) => setInwardRef(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Delivery Notes
                </label>
                <textarea
                  rows={2}
                  value={inwardNotes}
                  onChange={(e) => setInwardNotes(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsInwardModalOpen(false)}
                  disabled={isSubmitting}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 rounded-xl bg-emerald-600 py-2 text-xs font-bold text-white shadow-md hover:bg-emerald-500 disabled:opacity-50"
                >
                  {isSubmitting ? 'Recording...' : 'Record Inward'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Stock Adjustment Modal */}
      {isAdjustModalOpen && selectedItemForAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-zinc-900">Stock Adjustment</h3>
                <p className="text-xs text-zinc-500">
                  {selectedItemForAction.product_name} (Current: {selectedItemForAction.quantity})
                </p>
              </div>
              <button
                onClick={() => setIsAdjustModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleAdjustSubmit} className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Quantity Change (+ to add, - to subtract) *
                </label>
                <input
                  type="number"
                  step="1"
                  required
                  placeholder="e.g. -2 or +5"
                  value={adjustQtyChange}
                  onChange={(e) => setAdjustQtyChange(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs font-bold focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Mandatory Audit Reason *
                </label>
                <textarea
                  rows={2}
                  required
                  minLength={2}
                  placeholder="e.g. Discovered damaged garment during physical count"
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAdjustModalOpen(false)}
                  disabled={isSubmitting}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 rounded-xl bg-amber-500 py-2 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400 disabled:opacity-50"
                >
                  {isSubmitting ? 'Adjusting...' : 'Save Adjustment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Inventory Confirmation Modal */}
      {isDeleteModalOpen && itemToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center gap-3 border-b border-zinc-100 pb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
                <Trash2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-zinc-900">Delete Inventory Record</h3>
                <p className="text-xs text-zinc-500">Confirm store inventory removal</p>
              </div>
            </div>

            <div className="my-4 space-y-3">
              <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Product:</span>
                  <span className="font-bold text-zinc-900">{itemToDelete.product_name}</span>
                </div>
                {(itemToDelete.size || itemToDelete.color) && (
                  <div className="flex justify-between">
                    <span className="text-zinc-500 font-medium">Variation:</span>
                    <span className="font-semibold text-zinc-800">
                      {itemToDelete.size ? `Size ${itemToDelete.size}` : ''}
                      {itemToDelete.color ? ` (${itemToDelete.color})` : ''}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">SKU:</span>
                  <span className="font-mono text-zinc-700">{itemToDelete.sku || '—'}</span>
                </div>
                <div className="flex justify-between border-t border-zinc-200 pt-1.5">
                  <span className="text-zinc-500 font-medium">Available Quantity:</span>
                  <span className="font-black text-sm text-zinc-900">{itemToDelete.quantity} units</span>
                </div>
              </div>

              {itemToDelete.quantity > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-3 text-xs text-amber-800 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
                  <p>
                    <strong>Stock Warning:</strong> This record currently has{' '}
                    <strong>{itemToDelete.quantity} units</strong> in stock. Deleting this inventory record will
                    remove these units from the total store stock count.
                  </p>
                </div>
              )}

              <p className="text-xs text-zinc-500 leading-relaxed">
                The product and catalogue entry will remain safe and preserved. Only this inventory tracking record is removed.
              </p>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setIsDeleteModalOpen(false);
                  setItemToDelete(null);
                }}
                disabled={isDeleting}
                className="flex-1 rounded-xl border border-zinc-300 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteSubmit}
                disabled={isDeleting}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-rose-600 py-2.5 text-xs font-bold text-white shadow-md hover:bg-rose-500 disabled:opacity-50 transition-all"
              >
                {isDeleting ? (
                  <>
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <span>Delete Record</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
