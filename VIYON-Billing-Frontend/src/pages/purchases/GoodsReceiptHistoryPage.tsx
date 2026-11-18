import React, { useState, useEffect } from 'react';
import { ClipboardList, RefreshCw, Eye, X } from 'lucide-react';
import { GoodsReceipt } from '../../types';
import { purchaseService } from '../../services/purchaseService';
import { formatDateTime } from '../../utils/formatters';

export const GoodsReceiptHistoryPage: React.FC = () => {
  const [receipts, setReceipts] = useState<GoodsReceipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedGRN, setSelectedGRN] = useState<GoodsReceipt | null>(null);

  useEffect(() => {
    loadGRNHistory();
  }, []);

  const loadGRNHistory = async () => {
    setLoading(true);
    try {
      const res = await purchaseService.getReceiptHistory({ limit: 100 });
      setReceipts(res.items || []);
    } catch (err) {
      console.error('Failed to load GRN history', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-zinc-900 font-serif">
            Goods Receipt History (GRN)
          </h2>
          <p className="text-xs text-zinc-500">
            Historical log of all vendor shipment inspections, accepted inventory additions, and rejected damaged counts.
          </p>
        </div>

        <button
          onClick={loadGRNHistory}
          className="flex items-center gap-1.5 self-start sm:self-auto rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-700 shadow-sm hover:bg-zinc-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-2">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
            <p className="text-xs text-zinc-400">Loading GRN log...</p>
          </div>
        ) : receipts.length === 0 ? (
          <div className="p-8 text-center text-xs text-zinc-400">
            No goods receipt notes recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                <tr>
                  <th className="py-3 px-4">GRN Number</th>
                  <th className="py-3 px-4">PO Reference</th>
                  <th className="py-3 px-4">Supplier</th>
                  <th className="py-3 px-4">Receiving Date</th>
                  <th className="py-3 px-4 text-right">Accepted Units</th>
                  <th className="py-3 px-4 text-right">Rejected Units</th>
                  <th className="py-3 px-4">Received By</th>
                  <th className="py-3 px-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {receipts.map((grn) => (
                  <tr key={grn.id} className="hover:bg-zinc-50/60 transition-colors">
                    <td className="py-3 px-4 font-bold text-zinc-900">{grn.grn_number}</td>
                    <td className="py-3 px-4 font-mono text-zinc-500">{grn.po_number || '—'}</td>
                    <td className="py-3 px-4 text-zinc-800 font-medium">{grn.supplier_name || '—'}</td>
                    <td className="py-3 px-4 text-zinc-500">{formatDateTime(grn.receiving_date)}</td>
                    <td className="py-3 px-4 text-right font-bold text-emerald-600">
                      +{grn.total_accepted_quantity}
                    </td>
                    <td className="py-3 px-4 text-right font-bold text-rose-600">
                      {grn.total_rejected_quantity > 0 ? grn.total_rejected_quantity : 0}
                    </td>
                    <td className="py-3 px-4 text-zinc-600">{grn.received_by_user_name || 'Staff'}</td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={() => setSelectedGRN(grn)}
                        className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700"
                        title="View GRN Breakdown"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal */}
      {selectedGRN && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm">
          <div className="relative flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
              <div>
                <h3 className="text-base font-bold text-zinc-900">Goods Receipt Note: {selectedGRN.grn_number}</h3>
                <p className="text-xs text-zinc-500">PO: {selectedGRN.po_number} • Supplier: {selectedGRN.supplier_name}</p>
              </div>
              <button
                onClick={() => setSelectedGRN(null)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="grid grid-cols-3 gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-center text-xs">
                <div>
                  <span className="text-[10px] text-zinc-400 font-semibold uppercase">Total Received</span>
                  <p className="text-base font-black text-zinc-900">{selectedGRN.total_received_quantity}</p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-400 font-semibold uppercase">Accepted (Stock In)</span>
                  <p className="text-base font-black text-emerald-600">{selectedGRN.total_accepted_quantity}</p>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-400 font-semibold uppercase">Rejected (Damaged)</span>
                  <p className="text-base font-black text-rose-600">{selectedGRN.total_rejected_quantity}</p>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-bold text-zinc-900 mb-2">Item Inspection Details</h4>
                <div className="rounded-xl border border-zinc-200 overflow-x-auto">
                  <table className="w-full text-left text-xs min-w-[460px]">
                    <thead className="bg-zinc-50 text-zinc-600 border-b border-zinc-200 font-semibold">
                      <tr>
                        <th className="py-2 px-3">Item</th>
                        <th className="py-2 px-3 text-right">Accepted</th>
                        <th className="py-2 px-3 text-right">Rejected</th>
                        <th className="py-2 px-3">Rejection Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {selectedGRN.items?.map((item) => (
                        <tr key={item.id}>
                          <td className="py-2 px-3 font-semibold text-zinc-800">
                            {item.product_name}
                            {item.size && ` (Size: ${item.size})`}
                          </td>
                          <td className="py-2 px-3 text-right text-emerald-600 font-bold">{item.quantity_accepted}</td>
                          <td className="py-2 px-3 text-right text-rose-600 font-bold">{item.quantity_rejected}</td>
                          <td className="py-2 px-3 text-zinc-500">{item.rejection_reason || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="flex justify-end border-t border-zinc-200 bg-zinc-50 px-6 py-3">
              <button
                onClick={() => setSelectedGRN(null)}
                className="rounded-lg bg-zinc-900 px-4 py-1.5 text-xs font-bold text-white hover:bg-zinc-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
