import React, { useState, useEffect } from 'react';
import { X, Plus, Minus, Package, ShoppingCart } from 'lucide-react';
import { Product, ProductVariant } from '../../types';
import { formatCurrency } from '../../utils/formatters';

interface VariantSelectModalProps {
  product: Product | null;
  isOpen: boolean;
  onClose: () => void;
  onAddVariants: (
    product: Product,
    selected: Array<{ variant: ProductVariant; quantity: number }>
  ) => void;
}

export const VariantSelectModal: React.FC<VariantSelectModalProps> = ({
  product,
  isOpen,
  onClose,
  onAddVariants,
}) => {
  // Quantities mapped by variant ID: { [variantId]: number }
  const [quantities, setQuantities] = useState<Record<string, number>>({});

  // Reset quantities to 0 whenever modal opens or product changes
  useEffect(() => {
    if (product && isOpen) {
      const initial: Record<string, number> = {};
      product.variants.forEach((v) => {
        initial[v.id] = 0;
      });
      setQuantities(initial);
    }
  }, [product, isOpen]);

  if (!isOpen || !product) return null;

  const handleIncrement = (variantId: string, maxStock: number) => {
    setQuantities((prev) => {
      const current = prev[variantId] || 0;
      if (current >= maxStock) return prev;
      return { ...prev, [variantId]: current + 1 };
    });
  };

  const handleDecrement = (variantId: string) => {
    setQuantities((prev) => {
      const current = prev[variantId] || 0;
      if (current <= 0) return prev;
      return { ...prev, [variantId]: current - 1 };
    });
  };

  const handleInputChange = (variantId: string, rawVal: string, maxStock: number) => {
    const val = parseInt(rawVal, 10);
    if (isNaN(val) || val <= 0) {
      setQuantities((prev) => ({ ...prev, [variantId]: 0 }));
      return;
    }
    const clamped = Math.min(val, maxStock);
    setQuantities((prev) => ({ ...prev, [variantId]: clamped }));
  };

  // Calculated totals across selected variants
  const totalSelectedQty = Object.values(quantities).reduce((acc, q) => acc + q, 0);

  const totalSelectedAmount = product.variants.reduce((acc, v) => {
    const qty = quantities[v.id] || 0;
    const price = v.price_override ? Number(v.price_override) : Number(product.base_price);
    return acc + qty * price;
  }, 0);

  const handleConfirm = () => {
    if (totalSelectedQty === 0) return;

    const selections: Array<{ variant: ProductVariant; quantity: number }> = [];
    product.variants.forEach((v) => {
      const qty = quantities[v.id] || 0;
      if (qty > 0) {
        selections.push({ variant: v, quantity: qty });
      }
    });

    onAddVariants(product, selections);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-3 sm:p-4 backdrop-blur-sm">
      <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 sm:px-6 py-3 sm:py-4 bg-zinc-50/50">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-xl bg-zinc-100 border border-zinc-200 overflow-hidden flex items-center justify-center shrink-0">
              {product.product_image_url ? (
                <img
                  src={product.product_image_url}
                  alt={product.product_name}
                  className="h-full w-full object-cover"
                />
              ) : (
                <Package className="h-6 w-6 text-zinc-400" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-zinc-900">{product.product_name}</h3>
                {product.brand && (
                  <span className="rounded bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-600">
                    {product.brand}
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-500">
                Base Price: <span className="font-semibold text-zinc-800">{formatCurrency(product.base_price)}</span> • Select sizes & quantities to add
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Variants Selection Table */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-3">
          {product.variants.length === 0 ? (
            <div className="py-12 text-center text-xs text-zinc-500">
              <Package className="h-8 w-8 mx-auto text-zinc-300 mb-2" />
              No size variants configured for this product.
            </div>
          ) : (
            <div className="rounded-xl border border-zinc-200 overflow-x-auto shadow-sm">
              <table className="w-full text-left text-xs min-w-[460px]">
                <thead className="bg-zinc-50 text-zinc-600 font-semibold border-b border-zinc-200">
                  <tr>
                    <th className="py-3 px-4">Size</th>
                    <th className="py-3 px-4">SKU / Color</th>
                    <th className="py-3 px-4 text-right">Unit Price</th>
                    <th className="py-3 px-4 text-right">Available Stock</th>
                    <th className="py-3 px-4 text-center w-36">Quantity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {product.variants.map((v) => {
                    const price = v.price_override ? Number(v.price_override) : Number(product.base_price);
                    const isOutOfStock = v.current_stock <= 0;
                    const qty = quantities[v.id] || 0;

                    return (
                      <tr
                        key={v.id}
                        className={`transition-colors ${
                          isOutOfStock
                            ? 'bg-zinc-50/50 opacity-60'
                            : qty > 0
                            ? 'bg-amber-50/40'
                            : 'hover:bg-zinc-50/70'
                        }`}
                      >
                        <td className="py-3 px-4">
                          <span className="inline-flex items-center justify-center font-bold text-xs rounded-lg bg-zinc-900 text-white min-w-8 h-7 px-2">
                            {v.size}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="font-mono text-zinc-600 block">{v.sku}</span>
                          {v.color && (
                            <span className="text-[10px] text-zinc-400">{v.color}</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right font-bold text-zinc-900">
                          {formatCurrency(price)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {isOutOfStock ? (
                            <span className="rounded bg-rose-50 border border-rose-200 px-2 py-0.5 text-[10px] font-bold text-rose-700">
                              Out of stock
                            </span>
                          ) : v.current_stock <= v.low_stock_threshold ? (
                            <span className="rounded bg-amber-50 border border-amber-200 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                              {v.current_stock} left
                            </span>
                          ) : (
                            <span className="rounded bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                              {v.current_stock} in stock
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center justify-center">
                            <div className="flex items-center rounded-lg border border-zinc-200 bg-white shadow-2xs">
                              <button
                                type="button"
                                onClick={() => handleDecrement(v.id)}
                                disabled={isOutOfStock || qty <= 0}
                                className="p-1.5 text-zinc-500 hover:text-zinc-900 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                              >
                                <Minus className="h-3.5 w-3.5" />
                              </button>
                              <input
                                type="number"
                                min="0"
                                max={v.current_stock}
                                disabled={isOutOfStock}
                                value={qty}
                                onChange={(e) =>
                                  handleInputChange(v.id, e.target.value, v.current_stock)
                                }
                                className="w-12 text-center text-xs font-bold text-zinc-900 focus:outline-none disabled:bg-zinc-100"
                              />
                              <button
                                type="button"
                                onClick={() => handleIncrement(v.id, v.current_stock)}
                                disabled={isOutOfStock || qty >= v.current_stock}
                                className="p-1.5 text-zinc-500 hover:text-zinc-900 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                              >
                                <Plus className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal Footer & Total Summary */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-t border-zinc-200 bg-zinc-50/80 px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center gap-4 text-xs">
            <div>
              <span className="text-zinc-500 block text-[10px] uppercase font-semibold">Total Selected</span>
              <span className="font-extrabold text-sm text-zinc-900">{totalSelectedQty} Units</span>
            </div>
            <div className="h-7 w-px bg-zinc-300" />
            <div>
              <span className="text-zinc-500 block text-[10px] uppercase font-semibold">Selected Amount</span>
              <span className="font-extrabold text-sm text-amber-600">
                {formatCurrency(totalSelectedAmount)}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-zinc-300 bg-white px-4 py-2.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 transition-colors flex-1 sm:flex-none text-center"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={totalSelectedQty === 0}
              className="flex items-center justify-center gap-2 rounded-xl bg-amber-500 px-5 py-2.5 text-xs font-bold text-zinc-950 shadow-sm hover:bg-amber-400 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex-1 sm:flex-none text-center"
            >
              <ShoppingCart className="h-4 w-4" />
              <span>Add to Cart ({totalSelectedQty})</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
