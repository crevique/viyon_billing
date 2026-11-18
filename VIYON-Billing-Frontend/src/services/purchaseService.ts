import { apiClient } from './api';
import {
  GoodsReceipt,
  GoodsReceiptListResponse,
  PurchaseOrder,
  PurchaseOrderListResponse,
  PurchaseSummary,
  SupplierPayment,
  SupplierPaymentListResponse,
} from '../types';

export interface CreatePOPayload {
  supplier_id: string;
  expected_delivery_date?: string;
  notes?: string;
  items: Array<{
    product_id: string;
    variant_id?: string | null;
    quantity_ordered: number;
    unit_cost: number;
    discount_percent?: number;
    tax_percent?: number;
  }>;
}

export interface GoodsReceiptPayload {
  purchase_order_id: string;
  receiving_date?: string;
  supplier_invoice_ref?: string;
  delivery_reference?: string;
  notes?: string;
  items: Array<{
    purchase_order_item_id: string;
    quantity_received: number;
    quantity_accepted: number;
    quantity_rejected: number;
    rejection_reason?: string;
  }>;
}

export interface SupplierPaymentPayload {
  supplier_id: string;
  purchase_order_id?: string;
  payment_method: 'CASH' | 'UPI' | 'BANK_TRANSFER' | 'CHEQUE';
  amount: number;
  transaction_reference?: string;
  notes?: string;
}

export const purchaseService = {
  getSummary: async (): Promise<PurchaseSummary> => {
    const response = await apiClient.get<PurchaseSummary>('/purchases/summary');
    return response.data;
  },

  getOrders: async (params?: {
    supplier_id?: string;
    status_filter?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<PurchaseOrderListResponse> => {
    const response = await apiClient.get<PurchaseOrderListResponse>('/purchases/orders', { params });
    return response.data;
  },

  getOrderById: async (id: string): Promise<PurchaseOrder> => {
    const response = await apiClient.get<PurchaseOrder>(`/purchases/orders/${id}`);
    return response.data;
  },

  createOrder: async (payload: CreatePOPayload): Promise<PurchaseOrder> => {
    const response = await apiClient.post<PurchaseOrder>('/purchases/orders', payload);
    return response.data;
  },

  placeOrder: async (id: string): Promise<PurchaseOrder> => {
    const response = await apiClient.post<PurchaseOrder>(`/purchases/orders/${id}/place`);
    return response.data;
  },

  cancelOrder: async (id: string, reason: string): Promise<PurchaseOrder> => {
    const response = await apiClient.post<PurchaseOrder>(`/purchases/orders/${id}/cancel`, { reason });
    return response.data;
  },

  receiveGoods: async (payload: GoodsReceiptPayload): Promise<GoodsReceipt> => {
    const response = await apiClient.post<GoodsReceipt>('/purchases/receiving', payload);
    return response.data;
  },

  getReceiptHistory: async (params?: {
    purchase_order_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<GoodsReceiptListResponse> => {
    const response = await apiClient.get<GoodsReceiptListResponse>('/purchases/receiving', { params });
    return response.data;
  },

  recordPayment: async (payload: SupplierPaymentPayload): Promise<SupplierPayment> => {
    const response = await apiClient.post<SupplierPayment>('/purchases/payments', payload);
    return response.data;
  },

  getPayments: async (params?: {
    supplier_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<SupplierPaymentListResponse> => {
    const response = await apiClient.get<SupplierPaymentListResponse>('/purchases/payments', { params });
    return response.data;
  },

  confirmPayment: async (paymentId: string, notes?: string): Promise<SupplierPayment> => {
    const response = await apiClient.patch<SupplierPayment>(`/purchases/payments/${paymentId}/confirm`, { notes });
    return response.data;
  },

  deleteOrder: async (id: string): Promise<{ message: string; deleted: boolean }> => {
    const response = await apiClient.delete<{ message: string; deleted: boolean }>(`/purchases/orders/${id}`);
    return response.data;
  },
};
