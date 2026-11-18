import { apiClient } from './api';
import { Supplier, SupplierListResponse } from '../types';

export interface CreateSupplierPayload {
  company_name: string;
  contact_person?: string;
  phone: string;
  alternate_phone?: string;
  email?: string;
  gstin?: string;
  address?: string;
  city?: string;
  state?: string;
  pincode?: string;
  notes?: string;
}

export const supplierService = {
  getSuppliers: async (params?: {
    search?: string;
    is_active?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<SupplierListResponse> => {
    const response = await apiClient.get<SupplierListResponse>('/suppliers', { params });
    return response.data;
  },

  getSupplierById: async (id: string): Promise<Supplier> => {
    const response = await apiClient.get<Supplier>(`/suppliers/${id}`);
    return response.data;
  },

  createSupplier: async (payload: CreateSupplierPayload): Promise<Supplier> => {
    const response = await apiClient.post<Supplier>('/suppliers', payload);
    return response.data;
  },

  updateSupplier: async (id: string, payload: Partial<CreateSupplierPayload> & { is_active?: boolean }): Promise<Supplier> => {
    const response = await apiClient.patch<Supplier>(`/suppliers/${id}`, payload);
    return response.data;
  },
};
