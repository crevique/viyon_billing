import { apiClient } from './api';
import {
  InventoryItem,
  InventorySummary,
  StockMovementListResponse,
} from '../types';

export interface InventoryAdjustmentPayload {
  product_id: string;
  variant_id?: string | null;
  quantity_change: number;
  movement_type: 'PURCHASE' | 'ADJUSTMENT';
  reason: string;
  notes?: string;
}

export interface InventoryInwardPayload {
  product_id: string;
  variant_id?: string | null;
  quantity: number;
  purchase_reference?: string;
  supplier_name?: string;
  notes?: string;
}

export const inventoryService = {
  getInventory: async (params?: {
    page?: number;
    page_size?: number;
    search?: string;
    stock_status?: string;
    category_id?: string;
  }): Promise<{ items: InventoryItem[]; total: number }> => {
    const response = await apiClient.get('/inventory', { params });
    return response.data;
  },

  getSummary: async (): Promise<InventorySummary> => {
    const response = await apiClient.get<InventorySummary>('/inventory/summary');
    return response.data;
  },

  getLowStock: async (params?: { limit?: number; offset?: number }): Promise<{ items: InventoryItem[]; total: number }> => {
    const response = await apiClient.get('/inventory/low-stock', { params });
    return response.data;
  },

  adjustStock: async (payload: InventoryAdjustmentPayload): Promise<any> => {
    const response = await apiClient.post('/inventory/adjust', payload);
    return response.data;
  },

  inwardStock: async (payload: InventoryInwardPayload): Promise<any> => {
    const response = await apiClient.post('/inventory/inward', payload);
    return response.data;
  },

  getMovements: async (params?: {
    limit?: number;
    offset?: number;
    movement_type?: string;
    product_id?: string;
  }): Promise<StockMovementListResponse> => {
    const response = await apiClient.get<StockMovementListResponse>('/inventory/movements', { params });
    return response.data;
  },

  deleteInventory: async (inventoryId: string): Promise<{ message: string; deleted: boolean; inventory_id: string }> => {
    const response = await apiClient.delete<{ message: string; deleted: boolean; inventory_id: string }>(`/inventory/${inventoryId}`);
    return response.data;
  },

  deleteStockMovement: async (movementId: string): Promise<{ message: string; deleted: boolean; reversal_delta: number }> => {
    const response = await apiClient.delete<{ message: string; deleted: boolean; reversal_delta: number }>(`/inventory/movements/${movementId}`);
    return response.data;
  },
};
