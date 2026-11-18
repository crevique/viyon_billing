import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  ShoppingCart,
  Trash2,
  Plus,
  Minus,
  Barcode,
  Package,
  CreditCard,
  User,
  Tag,
  Receipt,
  RotateCcw,
  ChevronUp,
  ChevronDown,
} from 'lucide-react';
import { Product, ProductVariant, Category } from '../../types';
import { productService } from '../../services/productService';
import { billingService } from '../../services/billingService';
import { useCartStore } from '../../stores/useCartStore';
import { formatCurrency } from '../../utils/formatters';
import { PaymentModal } from '../../components/pos/PaymentModal';
import { VariantSelectModal } from '../../components/pos/VariantSelectModal';
import { ThermalReceiptModal } from '../../components/receipts/ThermalReceiptModal';

export const POSPage: React.FC = () => {
  // Products & Categories state
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);

  // Modals state
  const [variantModalProduct, setVariantModalProduct] = useState<Product | null>(null);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState<boolean>(false);
  const [completedBillId, setCompletedBillId] = useState<string | null>(null);
  const [isProcessingCheckout, setIsProcessingCheckout] = useState<boolean>(false);
  const [isMobileCartOpen, setIsMobileCartOpen] = useState<boolean>(false);

  // Cart store
  const {
    items: cartItems,
    customerName,
    customerPhone,
    billDiscount,
    notes,
    addItem,
    addMultipleVariants,
    updateQuantity,
    updateItemDiscount,
    removeItem,
    clearCart,
    setCustomer,
    setBillDiscount,
    setNotes,
    getSubtotal,
    getItemDiscountsTotal,
    getGrandTotal,
    getTotalItemsCount,
  } = useCartStore();

  const barcodeBuffer = useRef<string>('');
  const barcodeLastTime = useRef<number>(0);

  // Initial load
  useEffect(() => {
    loadCatalog();
  }, []);

  const loadCatalog = async () => {
    setLoading(true);
    try {
      const [prodRes, catRes] = await Promise.all([
        productService.getProducts({ page_size: 100, is_active: true, is_archived: false }),
        productService.getCategories(),
      ]);
      setProducts(prodRes.items || []);
      setCategories(catRes || []);
    } catch (err) {
      console.error('Failed to load products/categories', err);
    } finally {
      setLoading(false);
    }
  };

  // Barcode scanner listener (USB HID keyboard emulation)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // If user is focused on a text input, don't intercept standard typing
      const activeEl = document.activeElement;
      if (
        activeEl instanceof HTMLInputElement &&
        activeEl.type === 'text' &&
        !activeEl.classList.contains('barcode-search-input')
      ) {
        return;
      }

      const now = Date.now();
      if (now - barcodeLastTime.current > 100) {
        barcodeBuffer.current = '';
      }
      barcodeLastTime.current = now;

      if (e.key === 'Enter') {
        if (barcodeBuffer.current.length >= 3) {
          handleBarcodeScanned(barcodeBuffer.current);
          barcodeBuffer.current = '';
        }
      } else if (e.key.length === 1) {
        barcodeBuffer.current += e.key;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [products]);

  const handleBarcodeScanned = (code: string) => {
    const cleanCode = code.trim().toLowerCase();
    // Search products by barcode or SKU
    for (const p of products) {
      if (p.product_type === 'SIMPLE') {
        if (
          p.sku?.toLowerCase() === cleanCode ||
          p.barcode?.toLowerCase() === cleanCode
        ) {
          addItem(p, null, 1);
          return;
        }
      } else {
        for (const v of p.variants) {
          if (
            v.sku.toLowerCase() === cleanCode ||
            v.barcode?.toLowerCase() === cleanCode
          ) {
            addItem(p, v, 1);
            return;
          }
        }
      }
    }
  };

  const handleProductClick = (product: Product) => {
    if (product.product_type === 'VARIANT') {
      setVariantModalProduct(product);
    } else {
      if ((product.current_stock || 0) <= 0) {
        alert('This item is currently out of stock.');
        return;
      }
      addItem(product, null, 1);
    }
  };

  const filteredProducts = products.filter((p) => {
    const matchesCategory =
      selectedCategory === 'ALL' || p.category_id === selectedCategory;
    const matchesSearch =
      searchTerm === '' ||
      p.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (p.sku && p.sku.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (p.barcode && p.barcode.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (p.product_code && p.product_code.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesCategory && matchesSearch;
  });

  // Handle Checkout submission
  const handleCheckoutSubmit = async (
    payments: Array<{ method: 'CASH' | 'UPI'; amount: number; reference?: string }>
  ) => {
    if (cartItems.length === 0) return;
    setIsProcessingCheckout(true);

    try {
      // 1. Prepare bill items payload
      const itemsPayload = cartItems.map((item) => ({
        product_id: item.productId,
        variant_id: item.variantId || null,
        quantity: item.quantity,
        discount_amount: 0,
      }));

      // 2. Prepare payments payload for atomic transaction
      const paymentsPayload = payments.map((p) => ({
        payment_method: p.method,
        amount: p.amount,
        transaction_reference: p.reference,
        confirm_immediately: true,
      }));

      // 3. Atomically Create Bill and record Payments in one database transaction
      const createdBill = await billingService.createBill({
        customer_id: null,
        items: itemsPayload,
        discount_amount: billDiscount || 0,
        notes: notes ? `${notes} (Customer: ${customerName} ${customerPhone})` : (customerName ? `Customer: ${customerName} ${customerPhone}` : undefined),
        payments: paymentsPayload,
      });

      // 4. Success -> Open Receipt Modal & Reset Cart
      setIsPaymentModalOpen(false);
      setIsMobileCartOpen(false);
      setCompletedBillId(createdBill.id);
      clearCart();

      // 5. Reload product catalog in background to refresh real-time inventory counts
      loadCatalog();
    } catch (err: any) {
      console.error('Checkout error', err);
      throw err;
    } finally {
      setIsProcessingCheckout(false);
    }
  };

  const subtotal = getSubtotal();
  const itemDiscounts = getItemDiscountsTotal();
  const grandTotal = getGrandTotal();
  const totalCount = getTotalItemsCount();

  return (
    <div className="flex h-full flex-col lg:flex-row gap-4 overflow-hidden -m-3 sm:-m-6 lg:-m-8 p-3 sm:p-6 lg:p-8 relative">
      {/* LEFT SECTION: Catalog & Product Search */}
      <div className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
        {/* Search & Barcode Scan Bar */}
        <div className="border-b border-zinc-200 p-4">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                placeholder="Search products by Name, SKU, Code or Barcode..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full rounded-xl border border-zinc-200 bg-zinc-50 pl-10 pr-4 py-2.5 text-xs text-zinc-900 placeholder-zinc-400 focus:border-amber-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-amber-500"
              />
            </div>
            <div className="flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200/80 px-3 py-2 text-xs font-semibold text-amber-800">
              <Barcode className="h-4 w-4 text-amber-600" />
              <span className="hidden sm:inline">Scanner Ready</span>
            </div>
          </div>

          {/* Category Filter Pills */}
          <div className="mt-3 flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
            <button
              onClick={() => setSelectedCategory('ALL')}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all shrink-0 ${selectedCategory === 'ALL'
                ? 'bg-zinc-900 text-white shadow-sm'
                : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'
                }`}
            >
              All Items ({products.length})
            </button>
            {categories.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelectedCategory(c.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all shrink-0 ${selectedCategory === c.id
                  ? 'bg-zinc-900 text-white shadow-sm'
                  : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'
                  }`}
              >
                {c.name}
              </button>
            ))}
          </div>
        </div>

        {/* Product Cards Grid */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-4 pb-20 lg:pb-4 scrollbar-thin scrollbar-thumb-zinc-200">
          {loading ? (
            <div className="flex h-64 flex-col items-center justify-center gap-3">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
              <p className="text-xs text-zinc-500">Loading catalog...</p>
            </div>
          ) : filteredProducts.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center text-center">
              <Package className="h-10 w-10 text-zinc-300 mb-2" />
              <p className="text-sm font-semibold text-zinc-700">No products found</p>
              <p className="text-xs text-zinc-400">Try adjusting your search query or category filter</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3">
              {filteredProducts.map((p) => {
                const isOutOfStock =
                  p.product_type === 'SIMPLE'
                    ? (p.current_stock || 0) <= 0
                    : p.variants.every((v) => v.current_stock <= 0);

                return (
                  <div
                    key={p.id}
                    onClick={() => handleProductClick(p)}
                    className={`group relative flex flex-col justify-between rounded-xl border p-3.5 transition-all cursor-pointer ${isOutOfStock
                      ? 'border-zinc-200 bg-zinc-50/60 opacity-60'
                      : 'border-zinc-200 bg-white hover:border-amber-500 hover:shadow-md active:scale-98'
                      }`}
                  >
                    <div>
                      {/* Image / Monogram Thumbnail */}
                      <div className="relative mb-2.5 h-28 w-full overflow-hidden rounded-lg bg-zinc-100 flex items-center justify-center border border-zinc-100">
                        {p.product_image_url ? (
                          <img
                            src={p.product_image_url}
                            alt={p.product_name}
                            className="h-full w-full object-cover transition-transform group-hover:scale-105"
                          />
                        ) : (
                          <div className="flex flex-col items-center text-zinc-400">
                            <Package className="h-8 w-8 mb-1 stroke-[1.5]" />
                            <span className="text-[10px] font-semibold font-serif text-zinc-500 uppercase tracking-widest">
                              VIYON
                            </span>
                          </div>
                        )}
                        {/* Type Badge */}
                        <span className="absolute top-1.5 left-1.5 rounded bg-zinc-900/80 px-1.5 py-0.5 text-[9px] font-bold text-white uppercase tracking-wider backdrop-blur-xs">
                          {p.product_type}
                        </span>
                      </div>

                      <h4 className="text-xs font-bold text-zinc-900 line-clamp-2 leading-snug group-hover:text-amber-600 transition-colors">
                        {p.product_name}
                      </h4>
                      <p className="mt-0.5 text-[11px] font-mono text-zinc-400">
                        {p.sku || p.product_code || 'CODE'}
                      </p>
                    </div>

                    <div className="mt-3 flex items-center justify-between border-t border-zinc-100 pt-2">
                      <span className="text-xs font-extrabold text-zinc-900">
                        {formatCurrency(p.base_price)}
                      </span>
                      <span
                        className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${isOutOfStock
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-emerald-100 text-emerald-800'
                          }`}
                      >
                        {isOutOfStock
                          ? 'Out of Stock'
                          : p.product_type === 'VARIANT'
                            ? `${p.variants.length} Sizes`
                            : `${p.current_stock || 0} in stock`}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Mobile Floating Cart Summary Bar */}
      <div className="lg:hidden fixed bottom-3 left-3 right-3 z-30">
        <button
          type="button"
          onClick={() => setIsMobileCartOpen(true)}
          className="flex w-full items-center justify-between rounded-2xl bg-zinc-950 p-3.5 text-white shadow-2xl border border-zinc-800 active:scale-98 transition-all"
        >
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-amber-500 text-zinc-950 font-black text-xs shadow-sm">
              {totalCount}
            </div>
            <div className="text-left">
              <span className="text-xs font-bold block leading-tight">Current Cart</span>
              <span className="text-[10px] text-zinc-400">
                {totalCount === 1 ? '1 item in cart' : `${totalCount} items in cart`}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-black text-amber-400">
              {formatCurrency(grandTotal)}
            </span>
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-zinc-800 text-zinc-300">
              <ChevronUp className="h-4 w-4" />
            </div>
          </div>
        </button>
      </div>

      {/* Mobile Cart Backdrop */}
      {isMobileCartOpen && (
        <div
          className="fixed inset-0 z-40 bg-zinc-950/70 backdrop-blur-xs lg:hidden"
          onClick={() => setIsMobileCartOpen(false)}
        />
      )}

      {/* RIGHT SECTION: Cart Drawer & Checkout */}
      <div
        className={`flex flex-col bg-white shadow-xl transition-transform duration-300 ease-in-out shrink-0
          lg:static lg:w-96 lg:rounded-2xl lg:border lg:border-zinc-200 lg:shadow-sm lg:translate-y-0 lg:h-full lg:max-h-none lg:z-auto
          fixed inset-x-0 bottom-0 z-50 rounded-t-3xl max-h-[88vh] h-[88vh] border-t border-zinc-200 lg:h-auto
          ${isMobileCartOpen ? 'translate-y-0' : 'translate-y-full lg:translate-y-0 pointer-events-none lg:pointer-events-auto'}
        `}
      >
        {/* Cart Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 p-4">
          <div className="flex items-center gap-2">
            <ShoppingCart className="h-5 w-5 text-amber-500" />
            <h3 className="text-sm font-bold text-zinc-900">
              Current Cart ({totalCount})
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {cartItems.length > 0 && (
              <button
                onClick={clearCart}
                className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-rose-600 hover:bg-rose-50"
              >
                <RotateCcw className="h-3 w-3" />
                <span>Clear</span>
              </button>
            )}
            <button
              onClick={() => setIsMobileCartOpen(false)}
              className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 lg:hidden"
              aria-label="Close cart sheet"
            >
              <ChevronDown className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Customer Quick Capture */}
        <div className="border-b border-zinc-100 bg-zinc-50/70 p-3 text-xs">
          <div className="flex items-center gap-2 mb-1.5 text-zinc-700 font-semibold">
            <User className="h-3.5 w-3.5 text-zinc-400" />
            <span>Customer (Optional)</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="text"
              placeholder="Name (Walk-in)"
              value={customerName}
              onChange={(e) => setCustomer(null, e.target.value, customerPhone)}
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
            />
            <input
              type="text"
              placeholder="Phone number"
              value={customerPhone}
              onChange={(e) => setCustomer(null, customerName, e.target.value)}
              className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-800 focus:border-amber-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Cart Line Items List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2.5 scrollbar-thin scrollbar-thumb-zinc-200">
          {cartItems.length === 0 ? (
            <div className="flex h-56 flex-col items-center justify-center text-center">
              <ShoppingCart className="h-10 w-10 text-zinc-200 mb-2" />
              <p className="text-xs font-semibold text-zinc-600">Cart is empty</p>
              <p className="text-[11px] text-zinc-400">Scan barcode or select items from catalog</p>
            </div>
          ) : (
            cartItems.map((item) => (
              <div
                key={item.cartItemId}
                className="rounded-xl border border-zinc-200 bg-zinc-50/50 p-2.5 transition-all"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="truncate">
                    <p className="truncate text-xs font-bold text-zinc-900">
                      {item.productName}
                    </p>
                    <div className="flex items-center gap-1.5 text-[10px] text-zinc-500">
                      {item.size && (
                        <span className="rounded bg-zinc-200 px-1 py-0.2 font-semibold text-zinc-700">
                          {item.size}
                        </span>
                      )}
                      <span className="font-mono text-zinc-400">{item.sku}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => removeItem(item.cartItemId)}
                    className="p-1 text-zinc-400 hover:text-rose-600"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="mt-2.5 flex items-center justify-between">
                  {/* Quantity Controls */}
                  <div className="flex items-center rounded-lg border border-zinc-200 bg-white">
                    <button
                      onClick={() => updateQuantity(item.cartItemId, item.quantity - 1)}
                      className="p-1.5 text-zinc-500 hover:text-zinc-800"
                    >
                      <Minus className="h-3 w-3" />
                    </button>
                    <span className="w-8 text-center text-xs font-bold text-zinc-900">
                      {item.quantity}
                    </span>
                    <button
                      onClick={() => updateQuantity(item.cartItemId, item.quantity + 1)}
                      className="p-1.5 text-zinc-500 hover:text-zinc-800"
                    >
                      <Plus className="h-3 w-3" />
                    </button>
                  </div>

                  {/* Line Total */}
                  <div className="text-right">
                    <span className="text-xs font-bold text-zinc-900">
                      {formatCurrency(item.unitPrice * item.quantity)}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Bill Summary & Payment Trigger */}
        <div className="border-t border-zinc-200 bg-zinc-50/50 p-4 space-y-2">
          {/* Subtotal */}
          <div className="flex justify-between text-xs text-zinc-600">
            <span>Subtotal</span>
            <span className="font-medium text-zinc-900">{formatCurrency(subtotal)}</span>
          </div>

          {/* Overall Discount Input */}
          <div className="flex items-center justify-between text-xs">
            <span className="text-zinc-600 flex items-center gap-1">
              <Tag className="h-3 w-3 text-amber-500" />
              <span>Bill Discount</span>
            </span>
            <div className="flex items-center gap-1 w-24">
              <span className="text-zinc-400 text-xs">₹</span>
              <input
                type="number"
                min="0"
                step="1"
                placeholder="0"
                value={billDiscount || ''}
                onChange={(e) => setBillDiscount(parseFloat(e.target.value) || 0)}
                className="w-full rounded border border-zinc-200 bg-white px-1.5 py-0.5 text-right text-xs font-semibold focus:border-amber-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Grand Total */}
          <div className="border-t border-zinc-200 pt-2 flex items-center justify-between">
            <span className="text-sm font-bold text-zinc-900">Grand Total</span>
            <span className="text-xl font-extrabold text-amber-600">
              {formatCurrency(grandTotal)}
            </span>
          </div>

          {/* Action Button */}
          <button
            onClick={() => setIsPaymentModalOpen(true)}
            disabled={cartItems.length === 0}
            className="mt-2 w-full flex items-center justify-center gap-2 rounded-xl bg-amber-500 py-3 text-sm font-bold text-zinc-950 shadow-md transition-all hover:bg-amber-400 active:scale-98 disabled:opacity-50"
          >
            <CreditCard className="h-4 w-4" />
            <span>PAY {formatCurrency(grandTotal)}</span>
          </button>
        </div>
      </div>

      {/* Variant Selector Modal */}
      <VariantSelectModal
        product={variantModalProduct}
        isOpen={!!variantModalProduct}
        onClose={() => setVariantModalProduct(null)}
        onAddVariants={(p, selected) => addMultipleVariants(p, selected)}
      />

      {/* Payment Processing Modal */}
      <PaymentModal
        isOpen={isPaymentModalOpen}
        onClose={() => setIsPaymentModalOpen(false)}
        grandTotal={grandTotal}
        isProcessing={isProcessingCheckout}
        onSubmit={handleCheckoutSubmit}
      />

      {/* Receipt Modal on Completed Checkout */}
      {completedBillId && (
        <ThermalReceiptModal
          billId={completedBillId}
          onClose={() => setCompletedBillId(null)}
          isReprint={false}
        />
      )}
    </div>
  );
};
