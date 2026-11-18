import React, { useState, useEffect } from 'react';
import {
  FileSpreadsheet,
  Plus,
  Search,
  CheckCircle,
  XCircle,
  Eye,
  AlertTriangle,
  X,
  Truck,
  Send,
  Boxes,
  Trash2,
  RefreshCw,
} from 'lucide-react';
import { PurchaseOrder, Supplier, Product } from '../../types';
import { purchaseService, CreatePOPayload } from '../../services/purchaseService';
import { supplierService } from '../../services/supplierService';
import { productService } from '../../services/productService';
import { useAuthStore } from '../../stores/useAuthStore';
import { formatCurrency, formatDateTime, getStatusBadgeClass } from '../../utils/formatters';

export const PurchaseOrdersPage: React.FC = () => {
  const { role } = useAuthStore();
  const isOwner = role === 'OWNER' || role === 'ADMIN';

  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<PurchaseOrder | null>(null);
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Delete modal state
  const [orderToDelete, setOrderToDelete] = useState<PurchaseOrder | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  const handleDeleteOrder = async () => {
    if (!orderToDelete || isDeleting) return;

    setIsDeleting(true);
    try {
      const res = await purchaseService.deleteOrder(orderToDelete.id);
      setNotification({
        type: 'success',
        message: res.message || `Purchase Order ${orderToDelete.po_number} was successfully deleted.`,
      });
      setOrderToDelete(null);
      await loadOrders();
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to delete purchase order.';
      setNotification({
        type: 'error',
        message: errMsg,
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // New PO form state
  const [selectedSupplierId, setSelectedSupplierId] = useState('');
  const [expectedDate, setExpectedDate] = useState('');
  const [poNotes, setPoNotes] = useState('');
  const [poItems, setPoItems] = useState<
    Array<{
      product_id: string;
      variant_id?: string | null;
      quantity_ordered: number;
      unit_cost: number;
    }>
  >([]);

  useEffect(() => {
    loadOrders();
    loadDependencies();
  }, [statusFilter]);

  const loadOrders = async () => {
    setLoading(true);
    try {
      const res = await purchaseService.getOrders({
        status_filter: statusFilter || undefined,
        search: search.trim() || undefined,
      });
      setOrders(res.items || []);
    } catch (err) {
      console.error('Failed to load purchase orders', err);
    } finally {
      setLoading(false);
    }
  };

  const loadDependencies = async () => {
    try {
      const [suppRes, prodRes] = await Promise.all([
        supplierService.getSuppliers({ limit: 100 }),
        productService.getProducts({ page_size: 100 }),
      ]);
      setSuppliers(suppRes.items || []);
      setProducts(prodRes.items || []);
    } catch (err) {
      console.error('Failed to load PO dependencies', err);
    }
  };

  const handleOpenCreateModal = () => {
    setSelectedSupplierId(suppliers[0]?.id || '');
    setExpectedDate('');
    setPoNotes('');
    setPoItems([]);
    setIsCreateModalOpen(true);
  };

  const handleAddItemToPO = (productId: string, variantId?: string) => {
    const prod = products.find((p) => p.id === productId);
    if (!prod) return;

    const unitCost = Number(prod.cost_price || Math.floor(Number(prod.base_price) * 0.5));

    setPoItems([
      ...poItems,
      {
        product_id: productId,
        variant_id: variantId || null,
        quantity_ordered: 20,
        unit_cost: unitCost > 0 ? unitCost : 500,
      },
    ]);
  };

  const handleCreatePOSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSupplierId) {
      alert('Please select a supplier.');
      return;
    }
    if (poItems.length === 0) {
      alert('Please add at least one line item to the purchase order.');
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: CreatePOPayload = {
        supplier_id: selectedSupplierId,
        expected_delivery_date: expectedDate ? new Date(expectedDate).toISOString() : undefined,
        notes: poNotes.trim() || undefined,
        items: poItems,
      };

      await purchaseService.createOrder(payload);
      alert('Purchase Order created in DRAFT status.');
      setIsCreateModalOpen(false);
      loadOrders();
    } catch (err: any) {
      alert(`PO creation failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePlaceOrder = async (poId: string) => {
    if (!window.confirm('Place this Purchase Order with the supplier? Status will update to ORDERED.')) {
      return;
    }
    try {
      await purchaseService.placeOrder(poId);
      alert('Purchase Order placed with supplier.');
      loadOrders();
      if (selectedOrder?.id === poId) {
        setSelectedOrder(null);
      }
    } catch (err: any) {
      alert(`Failed to place order: ${err.message || 'Unknown error'}`);
    }
  };

  const handleCancelOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrder || cancelReason.trim().length < 2) return;

    try {
      await purchaseService.cancelOrder(selectedOrder.id, cancelReason.trim());
      alert('Purchase Order cancelled.');
      setIsCancelModalOpen(false);
      setSelectedOrder(null);
      setCancelReason('');
      loadOrders();
    } catch (err: any) {
      alert(`Cancellation failed: ${err.message || 'Unknown error'}`);
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
            Purchase Orders
          </h2>
          <p className="text-xs text-zinc-500">
            Create vendor procurement orders, track deliveries, and manage stock acquisition contracts.
          </p>
        </div>

        {isOwner && (
          <button
            onClick={handleOpenCreateModal}
            className="flex items-center gap-1.5 self-start sm:self-auto rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95"
          >
            <Plus className="h-4 w-4" />
            <span>Create Purchase Order</span>
          </button>
        )}
      </div>

      {/* Filter and Search */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              placeholder="Search by PO Number (e.g. PO-202611-0001) or supplier..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-zinc-200 bg-zinc-50 pl-9 pr-4 py-2 text-xs focus:border-amber-500 focus:bg-white focus:outline-none"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-700 focus:border-amber-500 focus:outline-none"
          >
            <option value="">Status: All Orders</option>
            <option value="DRAFT">DRAFT</option>
            <option value="ORDERED">ORDERED</option>
            <option value="PARTIALLY_RECEIVED">PARTIALLY_RECEIVED</option>
            <option value="RECEIVED">RECEIVED</option>
            <option value="CANCELLED">CANCELLED</option>
          </select>
        </div>
      </div>

      {/* PO Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading purchase orders...</p>
          </div>
        ) : orders.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            No purchase orders found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">PO Number</th>
                  <th className="py-3 px-4">Supplier</th>
                  <th className="py-3 px-4">Order Date</th>
                  <th className="py-3 px-4 text-right">Ordered Units</th>
                  <th className="py-3 px-4 text-right">Received Units</th>
                  <th className="py-3 px-4 text-right">Grand Total</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {orders.map((po) => (
                  <tr key={po.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-zinc-900">{po.po_number}</td>
                    <td className="py-3 px-4 font-medium text-zinc-800">{po.supplier_name}</td>
                    <td className="py-3 px-4 text-zinc-500">{formatDateTime(po.po_date)}</td>
                    <td className="py-3 px-4 text-right font-medium">{po.total_ordered_quantity}</td>
                    <td className="py-3 px-4 text-right text-emerald-700 font-medium">
                      {po.total_received_quantity}
                    </td>
                    <td className="py-3 px-4 text-right font-bold text-zinc-900">
                      {formatCurrency(po.grand_total)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getStatusBadgeClass(po.status)}`}>
                        {po.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => setSelectedOrder(po)}
                          className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
                          title="View Details"
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                        {isOwner && po.status === 'DRAFT' && (
                          <button
                            onClick={() => handlePlaceOrder(po.id)}
                            className="flex items-center gap-1 rounded bg-amber-500 px-2 py-1 text-[11px] font-bold text-zinc-950 hover:bg-amber-400"
                            title="Place Order"
                          >
                            <Send className="h-3 w-3" />
                            <span>Place</span>
                          </button>
                        )}
                        {isOwner && (
                          <button
                            onClick={() => setOrderToDelete(po)}
                            className="rounded-lg p-1.5 text-zinc-400 hover:bg-rose-50 hover:text-rose-600"
                            title="Delete Purchase Order"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* PO View Details Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
              <div>
                <h3 className="text-base font-bold text-zinc-900">Purchase Order {selectedOrder.po_number}</h3>
                <p className="text-xs text-zinc-500">Supplier: {selectedOrder.supplier_name}</p>
              </div>
              <button
                onClick={() => setSelectedOrder(null)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="grid grid-cols-3 gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-center text-xs">
                <div>
                  <span className="text-[10px] text-zinc-400 font-semibold uppercase">Total Value</span>
                  <p className="text-base font-black text-zinc-900">{formatCurrency(selectedOrder.grand_total)}</p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-400 font-semibold uppercase">Total Paid</span>
                  <p className="text-base font-black text-emerald-600">{formatCurrency(selectedOrder.total_paid)}</p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-400 font-semibold uppercase">Outstanding Due</span>
                  <p className="text-base font-black text-amber-600">{formatCurrency(selectedOrder.outstanding_amount)}</p>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-bold text-zinc-900 mb-2">Order Line Items</h4>
                <div className="rounded-xl border border-zinc-200 overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-50 text-zinc-600 border-b border-zinc-200 font-semibold">
                      <tr>
                        <th className="py-2 px-3">Item</th>
                        <th className="py-2 px-3 text-right">Ordered</th>
                        <th className="py-2 px-3 text-right">Received</th>
                        <th className="py-2 px-3 text-right">Unit Cost</th>
                        <th className="py-2 px-3 text-right">Line Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {selectedOrder.items?.map((item) => (
                        <tr key={item.id}>
                          <td className="py-2 px-3 font-semibold text-zinc-800">
                            {item.product_name}
                            {item.size && ` (Size: ${item.size})`}
                          </td>
                          <td className="py-2 px-3 text-right">{item.quantity_ordered}</td>
                          <td className="py-2 px-3 text-right text-emerald-700 font-medium">
                            {item.quantity_received}
                          </td>
                          <td className="py-2 px-3 text-right">{formatCurrency(item.unit_cost)}</td>
                          <td className="py-2 px-3 text-right font-bold text-zinc-900">
                            {formatCurrency(item.line_total)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-zinc-200 bg-zinc-50 px-6 py-3">
              <div className="flex items-center gap-2">
                {isOwner && (selectedOrder.status === 'DRAFT' || selectedOrder.status === 'ORDERED') && (
                  <button
                    onClick={() => setIsCancelModalOpen(true)}
                    className="rounded-lg px-3 py-1.5 text-xs font-bold text-amber-700 hover:bg-amber-50"
                  >
                    Cancel Order
                  </button>
                )}
                {isOwner && (
                  <button
                    onClick={() => {
                      setOrderToDelete(selectedOrder);
                      setSelectedOrder(null);
                    }}
                    className="rounded-lg px-3 py-1.5 text-xs font-bold text-rose-600 hover:bg-rose-50"
                  >
                    Delete Order
                  </button>
                )}
              </div>
              <button
                onClick={() => setSelectedOrder(null)}
                className="ml-auto rounded-lg bg-zinc-900 px-4 py-1.5 text-xs font-bold text-white hover:bg-zinc-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Purchase Order Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
              <h3 className="text-base font-bold text-zinc-900">Create New Purchase Order</h3>
              <button
                onClick={() => setIsCreateModalOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreatePOSubmit} className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Select Supplier *
                  </label>
                  <select
                    required
                    value={selectedSupplierId}
                    onChange={(e) => setSelectedSupplierId(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
                  >
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.company_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Expected Delivery Date
                  </label>
                  <input
                    type="date"
                    value={expectedDate}
                    onChange={(e) => setExpectedDate(e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Add Items Section */}
              <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-zinc-800">Order Line Items</span>
                  <select
                    onChange={(e) => {
                      if (!e.target.value) return;
                      const [prodId, varId] = e.target.value.split(':');
                      handleAddItemToPO(prodId, varId === 'null' ? undefined : varId);
                      e.target.value = '';
                    }}
                    className="rounded-lg border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-700 focus:outline-none"
                  >
                    <option value="">+ Add Product to PO...</option>
                    {products.map((p) => {
                      if (p.product_type === 'SIMPLE') {
                        return (
                          <option key={p.id} value={`${p.id}:null`}>
                            {p.product_name} ({p.sku})
                          </option>
                        );
                      }
                      return p.variants.map((v) => (
                        <option key={v.id} value={`${p.id}:${v.id}`}>
                          {p.product_name} - Size {v.size} ({v.sku})
                        </option>
                      ));
                    })}
                  </select>
                </div>

                {poItems.length === 0 ? (
                  <p className="text-xs text-zinc-400 py-3 text-center">
                    No items selected yet. Choose products from the dropdown above.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {poItems.map((item, idx) => {
                      const prod = products.find((p) => p.id === item.product_id);
                      const variant = prod?.variants.find((v) => v.id === item.variant_id);

                      return (
                        <div
                          key={idx}
                          className="flex items-center justify-between gap-3 rounded-lg border border-zinc-200 bg-white p-2.5 text-xs"
                        >
                          <div className="truncate flex-1">
                            <p className="font-bold text-zinc-900 truncate">{prod?.product_name}</p>
                            {variant && (
                              <p className="text-[11px] text-zinc-500 font-normal">
                                Size: {variant.size} • SKU: {variant.sku}
                              </p>
                            )}
                          </div>

                          <div className="flex items-center gap-2">
                            <div>
                              <span className="text-[10px] text-zinc-400">Qty:</span>
                              <input
                                type="number"
                                min="1"
                                value={item.quantity_ordered}
                                onChange={(e) => {
                                  const updated = [...poItems];
                                  updated[idx].quantity_ordered = parseInt(e.target.value) || 1;
                                  setPoItems(updated);
                                }}
                                className="w-16 rounded border px-2 py-1 text-right font-bold"
                              />
                            </div>

                            <div>
                              <span className="text-[10px] text-zinc-400">Cost: ₹</span>
                              <input
                                type="number"
                                min="0"
                                step="1"
                                value={item.unit_cost}
                                onChange={(e) => {
                                  const updated = [...poItems];
                                  updated[idx].unit_cost = parseFloat(e.target.value) || 0;
                                  setPoItems(updated);
                                }}
                                className="w-20 rounded border px-2 py-1 text-right font-bold"
                              />
                            </div>

                            <button
                              type="button"
                              onClick={() => setPoItems(poItems.filter((_, i) => i !== idx))}
                              className="text-zinc-400 hover:text-rose-600 p-1"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Procurement Notes
                </label>
                <textarea
                  rows={2}
                  placeholder="e.g. Festival stock dispatch instructions..."
                  value={poNotes}
                  onChange={(e) => setPoNotes(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2 border-t border-zinc-200 pt-4">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  disabled={isSubmitting}
                  className="flex-1 rounded-xl border border-zinc-300 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || poItems.length === 0}
                  className="flex-1 rounded-xl bg-amber-500 py-2.5 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400 disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Create Draft PO'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cancel PO Modal */}
      {isCancelModalOpen && selectedOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-base font-bold text-zinc-900 mb-2">Cancel Purchase Order</h3>
            <p className="text-xs text-zinc-600 mb-4">
              Cancelling order <strong>{selectedOrder.po_number}</strong>. This cannot be undone.
            </p>

            <form onSubmit={handleCancelOrder} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Cancellation Reason *
                </label>
                <textarea
                  rows={2}
                  required
                  placeholder="e.g. Supplier out of fabric, cancelled by mutual consent"
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-xs focus:border-rose-500 focus:outline-none"
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setIsCancelModalOpen(false)}
                  className="flex-1 rounded-xl border border-zinc-300 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
                >
                  Back
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl bg-rose-600 py-2 text-xs font-bold text-white shadow-md hover:bg-rose-500"
                >
                  Confirm Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Purchase Order Confirmation Modal */}
      {orderToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="flex items-center gap-3 border-b border-zinc-100 pb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
                <Trash2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-zinc-900">Delete Purchase Order</h3>
                <p className="text-xs text-zinc-500">Confirm purchase order deletion</p>
              </div>
            </div>

            <div className="my-4 space-y-3">
              <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">PO Number:</span>
                  <span className="font-bold text-zinc-900">{orderToDelete.po_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Supplier:</span>
                  <span className="font-semibold text-zinc-800">{orderToDelete.supplier_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Order Date:</span>
                  <span className="text-zinc-700">{formatDateTime(orderToDelete.po_date)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Status:</span>
                  <span className={`rounded border px-2 py-0.5 text-[10px] font-bold ${getStatusBadgeClass(orderToDelete.status)}`}>
                    {orderToDelete.status}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Ordered Quantity:</span>
                  <span className="font-semibold text-zinc-800">{orderToDelete.total_ordered_quantity} units</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 font-medium">Received Quantity:</span>
                  <span className={`font-semibold ${orderToDelete.total_received_quantity > 0 ? 'text-emerald-700' : 'text-zinc-500'}`}>
                    {orderToDelete.total_received_quantity} units
                  </span>
                </div>
                <div className="flex justify-between border-t border-zinc-200 pt-1.5">
                  <span className="text-zinc-500 font-medium">Grand Total:</span>
                  <span className="font-black text-sm text-zinc-900">{formatCurrency(orderToDelete.grand_total)}</span>
                </div>
              </div>

              {orderToDelete.total_received_quantity > 0 || orderToDelete.status === 'RECEIVED' || orderToDelete.status === 'PARTIALLY_RECEIVED' ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50/90 p-3 text-xs text-rose-800 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
                  <p>
                    <strong>Deletion Blocked:</strong> Goods have already been inspected and received against this Purchase Order
                    ({orderToDelete.total_received_quantity} units added to inventory). Deleting orders with received stock is
                    strictly prevented to protect inventory accuracy.
                  </p>
                </div>
              ) : (
                <p className="text-xs text-zinc-500 leading-relaxed">
                  Are you sure you want to permanently delete Purchase Order <strong>{orderToDelete.po_number}</strong>?
                  All associated line items will be removed. Supplier and product catalogues remain completely intact.
                </p>
              )}
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setOrderToDelete(null)}
                disabled={isDeleting}
                className="flex-1 rounded-xl border border-zinc-300 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              >
                Cancel
              </button>
              {!(orderToDelete.total_received_quantity > 0 || orderToDelete.status === 'RECEIVED' || orderToDelete.status === 'PARTIALLY_RECEIVED') && (
                <button
                  type="button"
                  onClick={handleDeleteOrder}
                  disabled={isDeleting}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-rose-600 py-2.5 text-xs font-bold text-white shadow-md hover:bg-rose-500 disabled:opacity-50 transition-all"
                >
                  {isDeleting ? (
                    <>
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                      <span>Deleting...</span>
                    </>
                  ) : (
                    <span>Delete Purchase Order</span>
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
