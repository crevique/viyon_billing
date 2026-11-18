import { apiClient } from './api';
import {
  DailyCashRegister,
  DailySalesSummary,
  Expense,
  ExpenseListResponse,
  ExpenseReportResponse,
  FinancialOverview,
  SalesReportResponse,
} from '../types';

export interface CreateExpensePayload {
  expense_title: string;
  category: string;
  amount: number;
  payment_method: 'CASH' | 'UPI' | 'CARD';
  expense_date?: string;
  description?: string;
  reference_number?: string;
}

export const financeService = {
  getOverview: async (params?: {
    preset?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<FinancialOverview> => {
    const response = await apiClient.get<FinancialOverview>('/finance/overview', { params });
    return response.data;
  },

  getSalesReport: async (params?: {
    preset?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<SalesReportResponse> => {
    const response = await apiClient.get<SalesReportResponse>('/finance/sales-report', { params });
    return response.data;
  },

  getExpenseReport: async (params?: {
    preset?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<ExpenseReportResponse> => {
    const response = await apiClient.get<ExpenseReportResponse>('/finance/expense-report', { params });
    return response.data;
  },

  downloadPdfReport: async (params?: {
    preset?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<void> => {
    const response = await apiClient.get('/finance/reports/export/pdf', {
      params,
      responseType: 'blob',
    });
    const blob = new Blob([response.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const presetName = params?.preset || 'today';
    link.setAttribute('download', `VIYON-Sales-Expenses-Report-${presetName}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.parentNode?.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  getDailySummary: async (date?: string): Promise<DailySalesSummary> => {
    const response = await apiClient.get<DailySalesSummary>('/finance/daily-summary', {
      params: date ? { business_date: date } : undefined,
    });
    return response.data;
  },

  getExpenses: async (params?: {
    category?: string;
    payment_method?: string;
    start_date?: string;
    end_date?: string;
    is_voided?: boolean;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<ExpenseListResponse> => {
    const response = await apiClient.get<ExpenseListResponse>('/expenses', { params });
    return response.data;
  },

  createExpense: async (payload: CreateExpensePayload): Promise<Expense> => {
    const response = await apiClient.post<Expense>('/expenses', payload);
    return response.data;
  },

  voidExpense: async (id: string, void_reason: string): Promise<Expense> => {
    const response = await apiClient.patch<Expense>(`/expenses/${id}/void`, { void_reason });
    return response.data;
  },

  // Daily Cash Register
  openCashRegister: async (payload: { opening_cash: number; opening_notes?: string }): Promise<DailyCashRegister> => {
    const response = await apiClient.post<DailyCashRegister>('/finance/cash/opening', payload);
    return response.data;
  },

  getTodayRegister: async (dateStr: string): Promise<DailyCashRegister> => {
    const response = await apiClient.get<DailyCashRegister>(`/finance/cash/${dateStr}`);
    return response.data;
  },

  addCashMovement: async (
    registerId: string,
    payload: { movement_type: 'INFLOW' | 'OUTFLOW'; amount: number; reason: string }
  ): Promise<any> => {
    const response = await apiClient.post(`/finance/cash/${registerId}/movements`, payload);
    return response.data;
  },

  closeCashRegister: async (
    registerId: string,
    payload: { actual_closing_cash: number; closing_notes?: string }
  ): Promise<DailyCashRegister> => {
    const response = await apiClient.post<DailyCashRegister>(`/finance/cash/${registerId}/close`, payload);
    return response.data;
  },

  getCashHistory: async (params?: { page?: number; page_size?: number }): Promise<{ items: DailyCashRegister[]; total: number }> => {
    const response = await apiClient.get('/finance/cash/history', { params });
    return response.data;
  },
};
