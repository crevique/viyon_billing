import React, { useState, useEffect } from 'react';
import { PackageCheck, Search, CheckCircle, AlertCircle, ArrowRight, X } from 'lucide-react';
import { PurchaseOrder, GoodsReceiptPayload } from '../../types';
import { purchaseService } from '../../services/purchaseService';
import { formatDateTime } from '../../utils/formatters';

export const GoodsReceivingPage: React.FC = () => {
  const [activeOrders, setActiveOrders] = useState<PurchaseOrder[]>([]);
  const [selectedPO, setSelectedPO] = useState<PurchaseOrder | null>(null);
  const [loading, setLoading] = useState(true);

  // Receiving Form State
  const [invoiceRef, setInvoiceRef] = useState('');
  const [deliveryRef, setDeliveryRef] = useState('');
  const [receivingNotes, setReceivingNotes] = useState('');
  const [receiptLines, setReceiptLines] = useState<
    Record<
      string,
      {
        received: number;
        accepted: number;
        rejected: number;
        rejectionReason: string;
      }
    >
  >({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    loadActiveOrders();
  }, []);

  const loadActiveOrders = async () => {
    setLoading(true);
    try {
      // Fetch orders that are in ORDERED or PARTIALLY_RECEIVED status
      const res = await purchaseService.getOrders({ limit: 100 });
      const eligible = (res.items || []).filter(
        (po) => po.status === 'ORDERED' || po.status === 'PARTIALLY_RECEIVED'
      );
      setActiveOrders(eligible);
    } catch (err) {
      console.error('Failed to load eligible purchase orders', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPO = (po: PurchaseOrder) => {
    setSelectedPO(po);
    const initialLines: typeof receiptLines = {};

    po.items?.forEach((item) => {
      const pendingQty = Math.max(0, item.quantity_ordered - item.quantity_received);
      initialLines[item.id] = {
        received: pendingQty,
        accepted: pendingQty,
        rejected: 0,
        rejectionReason: '',
      };
    });

    setReceiptLines(initialLines);
    setInvoiceRef('');
    setDeliveryRef('');
    setReceivingNotes('');
  };

  const handleLineChange = (
    itemId: string,
    field: 'accepted' | 'rejected' | 'rejectionReason',
    value: any
  ) => {
    const current = receiptLines[itemId] || { received: 0, accepted: 0, rejected: 0, rejectionReason: '' };
    const updated = { ...current };

    if (field === 'accepted') {
      const acceptedVal = Math.max(0, parseInt(value) || 0);
      updated.accepted = acceptedVal;
      updated.received = acceptedVal + updated.rejected;
    } else if (field === 'rejected') {
      const rejectedVal = Math.max(0, parseInt(value) || 0);
      updated.rejected = rejectedVal;
      updated.received = updated.accepted + rejectedVal;
    } else if (field === 'rejectionReason') {
      updated.rejectionReason = value;
    }

    setReceiptLines({
      ...receiptLines,
      [itemId]: updated,
    });
  };

  const handleSubmitGRN = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPO) return;

    // Validate rejected lines have reasons
    for (const [itemId, line] of Object.entries(receiptLines)) {
      if (line.rejected > 0 && !line.rejectionReason.trim()) {
        const item = selectedPO.items?.find((i) => i.id === itemId);
        alert(`Please specify a rejection/damage reason for ${item?.product_name || 'item'}.`);
        return;
      }
    }

    const itemsPayload = Object.entries(receiptLines).map(([itemId, line]) => ({
      purchase_order_item_id: itemId,
      quantity_received: line.received,
      quantity_accepted: line.accepted,
      quantity_rejected: line.rejected,
      rejection_reason: line.rejected > 0 ? line.rejectionReason.trim() : undefined,
    }));

    if (itemsPayload.every((i) => i.quantity_received === 0)) {
      alert('Cannot receive an empty delivery note with zero items.');
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: GoodsReceiptPayload = {
        purchase_order_id: selectedPO.id,
        supplier_invoice_ref: invoiceRef.trim() || undefined,
        delivery_reference: deliveryRef.trim() || undefined,
        notes: receivingNotes.trim() || undefined,
        items: itemsPayload,
      };

      const grn = await purchaseService.receiveGoods(payload);
      alert(`Goods Receipt Note ${grn.grn_number} created successfully! Accepted inventory has been added to stock.`);
      setSelectedPO(null);
      loadActiveOrders();
    } catch (err: any) {
      alert(`Receiving failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
          Goods Receiving (GRN Inspection)
        </h2>
        <p className="text-xs text-zinc-500">
          Inspect physical vendor shipments, separate accepted garments from damaged/rejected goods, and update store inventory.
        </p>
      </div>

      {!selectedPO ? (
        /* Orders pending receiving list */
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-bold text-zinc-900 mb-3">
            Active Purchase Orders Pending Delivery ({activeOrders.length})
          </h3>

          {loading ? (
            <div className="flex h-40 flex-col items-center justify-center gap-2">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
              <p className="text-xs text-zinc-400">Loading pending orders...</p>
            </div>
          ) : activeOrders.length === 0 ? (
            <div className="py-12 text-center text-xs text-zinc-400">
              No orders are currently in transit or awaiting delivery.
            </div>
          ) : (
            <div className="divide-y divide-zinc-100">
              {activeOrders.map((po) => (
                <div
                  key={po.id}
                  className="py-3 flex items-center justify-between hover:bg-zinc-50/50 p-2 rounded-xl transition-colors"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-zinc-900">{po.po_number}</span>
                      <span className="rounded bg-amber-50 text-amber-800 font-semibold px-2 py-0.5 text-[10px]">
                        {po.status}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-600 mt-0.5">
                      Supplier: <strong>{po.supplier_name}</strong> • Ordered {formatDateTime(po.po_date)}
                    </p>
                    <p className="text-[11px] text-zinc-400 mt-0.5">
                      Progress: {po.total_received_quantity} of {po.total_ordered_quantity} items received
                    </p>
                  </div>

                  <button
                    onClick={() => handleSelectPO(po)}
                    className="flex items-center gap-1.5 rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95"
                  >
                    <span>Receive Shipment</span>
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* GRN Inspection Form */
        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm space-y-6">
          <div className="flex items-center justify-between border-b border-zinc-100 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <PackageCheck className="h-5 w-5 text-amber-500" />
                <h3 className="text-base font-bold text-zinc-900">
                  Inspect Delivery: PO {selectedPO.po_number}
                </h3>
              </div>
              <p className="text-xs text-zinc-500">Vendor: {selectedPO.supplier_name}</p>
            </div>
            <button
              onClick={() => setSelectedPO(null)}
              className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <form onSubmit={handleSubmitGRN} className="space-y-6">
            {/* References */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Supplier Invoice Number
                </label>
                <input
                  type="text"
                  placeholder="e.g. INV-2026-99"
                  value={invoiceRef}
                  onChange={(e) => setInvoiceRef(e.target.value)}
                  className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Delivery Challan / Transporter LR
                </label>
                <input
                  type="text"
                  placeholder="e.g. LR-40192"
                  value={deliveryRef}
                  onChange={(e) => setDeliveryRef(e.target.value)}
                  className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Receiving Notes
                </label>
                <input
                  type="text"
                  placeholder="e.g. Box 2 inspected, minor carton crush"
                  value={receivingNotes}
                  onChange={(e) => setReceivingNotes(e.target.value)}
                  className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Line Items Inspection Grid */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-zinc-800 uppercase tracking-wider">
                Product Line Item Inspection & Verification
              </h4>

              <div className="rounded-xl border border-zinc-200 overflow-x-auto">
                <table className="w-full text-left text-xs min-w-[560px]">
                  <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                    <tr>
                      <th className="py-2.5 px-3">Item Details</th>
                      <th className="py-2.5 px-3 text-right">Ordered</th>
                      <th className="py-2.5 px-3 text-right">Prev. Received</th>
                      <th className="py-2.5 px-3 text-right">Accepted Qty</th>
                      <th className="py-2.5 px-3 text-right">Rejected Qty</th>
                      <th className="py-2.5 px-3">Rejection Explanation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100">
                    {selectedPO.items?.map((item) => {
                      const line = receiptLines[item.id] || {
                        received: 0,
                        accepted: 0,
                        rejected: 0,
                        rejectionReason: '',
                      };
                      return (
                        <tr key={item.id} className="hover:bg-zinc-50/50">
                          <td className="py-2.5 px-3">
                            <span className="font-bold text-zinc-900">{item.product_name}</span>
                            {item.size && (
                              <p className="text-[11px] text-zinc-500">Size: {item.size}</p>
                            )}
                          </td>
                          <td className="py-2.5 px-3 text-right font-medium">{item.quantity_ordered}</td>
                          <td className="py-2.5 px-3 text-right text-zinc-500">{item.quantity_received}</td>
                          <td className="py-2.5 px-3 text-right">
                            <input
                              type="number"
                              min="0"
                              value={line.accepted}
                              onChange={(e) => handleLineChange(item.id, 'accepted', e.target.value)}
                              className="w-16 rounded border border-emerald-300 bg-emerald-50/50 px-2 py-1 text-right font-bold text-emerald-800 focus:outline-none"
                            />
                          </td>
                          <td className="py-2.5 px-3 text-right">
                            <input
                              type="number"
                              min="0"
                              value={line.rejected}
                              onChange={(e) => handleLineChange(item.id, 'rejected', e.target.value)}
                              className="w-16 rounded border border-rose-300 bg-rose-50/50 px-2 py-1 text-right font-bold text-rose-800 focus:outline-none"
                            />
                          </td>
                          <td className="py-2.5 px-3">
                            <input
                              type="text"
                              placeholder={line.rejected > 0 ? 'Mandatory damage explanation' : 'Optional notes'}
                              value={line.rejectionReason}
                              onChange={(e) => handleLineChange(item.id, 'rejectionReason', e.target.value)}
                              className={`w-full rounded border px-2 py-1 text-xs focus:outline-none ${
                                line.rejected > 0 && !line.rejectionReason.trim()
                                  ? 'border-rose-400 bg-rose-50'
                                  : 'border-zinc-200'
                              }`}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-zinc-200 pt-4">
              <button
                type="button"
                onClick={() => setSelectedPO(null)}
                className="rounded-xl border border-zinc-300 px-4 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
              >
                Back to Pending Orders
              </button>

              <button
                type="submit"
                disabled={isSubmitting}
                className="flex items-center gap-2 rounded-xl bg-amber-500 px-6 py-2.5 text-xs font-bold text-zinc-950 shadow-md hover:bg-amber-400 active:scale-95 disabled:opacity-50"
              >
                <CheckCircle className="h-4 w-4" />
                <span>{isSubmitting ? 'Recording GRN...' : 'Confirm Goods Acceptance'}</span>
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
