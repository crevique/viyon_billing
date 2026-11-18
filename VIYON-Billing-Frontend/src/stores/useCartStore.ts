import { create } from 'zustand';
import { Product, ProductVariant } from '../types';

export interface CartLineItem {
  cartItemId: string; // unique string for line (product_id + (variant_id || ''))
  productId: string;
  variantId?: string | null;
  productName: string;
  sku: string;
  size?: string;
  color?: string;
  unitPrice: number;
  quantity: number;
  maxStock: number;
  discountAmount: number; // line discount
  taxPercent: number;
}

interface CartState {
  items: CartLineItem[];
  customerId: string | null;
  customerName: string;
  customerPhone: string;
  billDiscount: number;
  notes: string;

  // Actions
  addItem: (product: Product, variant?: ProductVariant | null, qty?: number) => void;
  addMultipleVariants: (
    product: Product,
    selections: Array<{ variant: ProductVariant; quantity: number }>
  ) => void;
  updateQuantity: (cartItemId: string, qty: number) => void;
  updateItemDiscount: (cartItemId: string, discount: number) => void;
  removeItem: (cartItemId: string) => void;
  clearCart: () => void;
  setCustomer: (id: string | null, name: string, phone: string) => void;
  setBillDiscount: (amount: number) => void;
  setNotes: (notes: string) => void;

  // Computed Totals
  getSubtotal: () => number;
  getItemDiscountsTotal: () => number;
  getGrandTotal: () => number;
  getTotalItemsCount: () => number;
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
  customerId: null,
  customerName: '',
  customerPhone: '',
  billDiscount: 0,
  notes: '',

  addItem: (product: Product, variant?: ProductVariant | null, qty = 1) => {
    const items = [...get().items];
    const variantId = variant?.id || null;
    const cartItemId = variantId ? `${product.id}-${variantId}` : product.id;

    const unitPrice = variant?.price_override
      ? Number(variant.price_override)
      : Number(product.base_price);

    const maxStock = variant ? variant.current_stock : (product.current_stock || 9999);
    const sku = variant ? variant.sku : (product.sku || 'SKU-NONE');

    const existingIndex = items.findIndex((i) => i.cartItemId === cartItemId);

    if (existingIndex > -1) {
      const existing = items[existingIndex];
      const newQty = existing.quantity + qty;
      if (newQty > maxStock) {
        alert(`Cannot add more than available stock (${maxStock}) for ${product.product_name}`);
        return;
      }
      items[existingIndex] = {
        ...existing,
        quantity: newQty,
      };
    } else {
      if (qty > maxStock) {
        alert(`Cannot add more than available stock (${maxStock}) for ${product.product_name}`);
        return;
      }
      items.push({
        cartItemId,
        productId: product.id,
        variantId,
        productName: product.product_name,
        sku,
        size: variant?.size,
        color: variant?.color,
        unitPrice,
        quantity: qty,
        maxStock,
        discountAmount: 0,
        taxPercent: 0,
      });
    }

    set({ items });
  },

  addMultipleVariants: (
    product: Product,
    selections: Array<{ variant: ProductVariant; quantity: number }>
  ) => {
    const items = [...get().items];

    for (const sel of selections) {
      if (sel.quantity <= 0) continue;
      const variant = sel.variant;
      const cartItemId = `${product.id}-${variant.id}`;
      const unitPrice = variant.price_override
        ? Number(variant.price_override)
        : Number(product.base_price);
      const maxStock = variant.current_stock;
      const sku = variant.sku;

      const existingIndex = items.findIndex((i) => i.cartItemId === cartItemId);
      if (existingIndex > -1) {
        const existing = items[existingIndex];
        const newQty = existing.quantity + sel.quantity;
        if (newQty > maxStock) {
          alert(
            `Quantity for size ${variant.size} exceeds available stock (${maxStock}). Adding max available (${maxStock}).`
          );
          items[existingIndex] = {
            ...existing,
            quantity: maxStock,
          };
        } else {
          items[existingIndex] = {
            ...existing,
            quantity: newQty,
          };
        }
      } else {
        const finalQty = Math.min(sel.quantity, maxStock);
        if (sel.quantity > maxStock) {
          alert(
            `Quantity for size ${variant.size} exceeds available stock (${maxStock}). Adding max available (${maxStock}).`
          );
        }
        items.push({
          cartItemId,
          productId: product.id,
          variantId: variant.id,
          productName: product.product_name,
          sku,
          size: variant.size,
          color: variant.color,
          unitPrice,
          quantity: finalQty,
          maxStock,
          discountAmount: 0,
          taxPercent: 0,
        });
      }
    }

    set({ items });
  },

  updateQuantity: (cartItemId: string, qty: number) => {
    if (qty <= 0) {
      get().removeItem(cartItemId);
      return;
    }
    const items = get().items.map((item) => {
      if (item.cartItemId === cartItemId) {
        const clampedQty = Math.min(qty, item.maxStock);
        if (qty > item.maxStock) {
          alert(`Quantity limited to available stock (${item.maxStock})`);
        }
        return { ...item, quantity: clampedQty };
      }
      return item;
    });
    set({ items });
  },

  updateItemDiscount: (cartItemId: string, discount: number) => {
    const items = get().items.map((item) => {
      if (item.cartItemId === cartItemId) {
        const maxLineTotal = item.unitPrice * item.quantity;
        return {
          ...item,
          discountAmount: Math.min(Math.max(0, discount), maxLineTotal),
        };
      }
      return item;
    });
    set({ items });
  },

  removeItem: (cartItemId: string) => {
    set({ items: get().items.filter((i) => i.cartItemId !== cartItemId) });
  },

  clearCart: () => {
    set({
      items: [],
      customerId: null,
      customerName: '',
      customerPhone: '',
      billDiscount: 0,
      notes: '',
    });
  },

  setCustomer: (id: string | null, name: string, phone: string) => {
    set({ customerId: id, customerName: name, customerPhone: phone });
  },

  setBillDiscount: (amount: number) => {
    set({ billDiscount: Math.max(0, amount) });
  },

  setNotes: (notes: string) => {
    set({ notes });
  },

  getSubtotal: () => {
    return get().items.reduce((acc, item) => acc + item.unitPrice * item.quantity, 0);
  },

  getItemDiscountsTotal: () => {
    return get().items.reduce((acc, item) => acc + item.discountAmount, 0);
  },

  getGrandTotal: () => {
    const subtotal = get().getSubtotal();
    const billDiscount = get().billDiscount;
    const total = subtotal - billDiscount;
    return Math.max(0, total);
  },

  getTotalItemsCount: () => {
    return get().items.reduce((acc, item) => acc + item.quantity, 0);
  },
}));
