import { apiClient } from './api';
import {
  Bill,
  BillCreateItem,
  BillListResponse,
  Payment,
  PaymentListResponse,
  ReceiptPreviewOut,
} from '../types';

export interface CreateBillPayload {
  customer_id?: string | null;
  items: Array<{
    product_id: string;
    variant_id?: string | null;
    quantity: number;
    discount_amount?: number;
  }>;
  discount_amount?: number;
  notes?: string;
  payments?: Array<{
    payment_method: 'CASH' | 'UPI';
    amount: number;
    transaction_reference?: string;
    notes?: string;
    confirm_immediately?: boolean;
  }>;
}

export interface RecordPaymentPayload {
  payment_method: 'CASH' | 'UPI';
  amount: number;
  transaction_reference?: string;
  notes?: string;
  confirm_immediately?: boolean;
}

export const billingService = {
  createBill: async (payload: CreateBillPayload): Promise<Bill> => {
    const response = await apiClient.post<Bill>('/bills', payload);
    return response.data;
  },

  getBills: async (params?: {
    page?: number;
    page_size?: number;
    status?: string;
    payment_status?: string;
    start_date?: string;
    end_date?: string;
    search?: string;
  }): Promise<BillListResponse> => {
    const response = await apiClient.get<BillListResponse>('/bills', { params });
    return response.data;
  },

  getBillById: async (billId: string): Promise<Bill> => {
    const response = await apiClient.get<Bill>(`/bills/${billId}`);
    return response.data;
  },

  cancelBill: async (billId: string, reason: string): Promise<Bill> => {
    const response = await apiClient.patch<Bill>(`/bills/${billId}/cancel`, { reason });
    return response.data;
  },

  recordPayment: async (billId: string, payload: RecordPaymentPayload): Promise<Payment> => {
    const response = await apiClient.post<Payment>(`/bills/${billId}/payments`, payload);
    return response.data;
  },

  getBillPayments: async (billId: string): Promise<Payment[]> => {
    const response = await apiClient.get<Payment[]>(`/bills/${billId}/payments`);
    return response.data;
  },

  listPayments: async (params?: {
    payment_method?: string;
    payment_status?: string;
    bill_number?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaymentListResponse> => {
    const response = await apiClient.get<PaymentListResponse>('/payments', { params });
    return response.data;
  },

  confirmPayment: async (paymentId: string, notes?: string): Promise<Payment> => {
    const response = await apiClient.patch<Payment>(`/payments/${paymentId}/confirm`, { notes });
    return response.data;
  },

  rejectPayment: async (paymentId: string, rejection_reason: string, notes?: string): Promise<Payment> => {
    const response = await apiClient.patch<Payment>(`/payments/${paymentId}/reject`, {
      rejection_reason,
      notes,
    });
    return response.data;
  },

  getReceipt: async (billId: string, is_reprint: boolean = false): Promise<ReceiptPreviewOut> => {
    const response = await apiClient.get<ReceiptPreviewOut>(`/bills/${billId}/receipt/preview`, {
      params: { is_reprint },
    });
    return response.data;
  },

  recordPrintAudit: async (billId: string, is_reprint: boolean = false): Promise<any> => {
    const response = await apiClient.post(`/bills/${billId}/receipt/print-audit`, { is_reprint });
    return response.data;
  },
};
