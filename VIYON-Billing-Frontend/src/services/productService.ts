import { apiClient } from './api';
import {
  Category,
  Product,
  ProductCreatePayload,
  ProductListResponse,
  ProductVariant,
  Subcategory,
} from '../types';

export const productService = {
  getProducts: async (params?: {
    page?: number;
    page_size?: number;
    limit?: number;
    offset?: number;
    search?: string;
    category_id?: string;
    is_active?: boolean;
    is_archived?: boolean;
    include_inactive?: boolean;
    include_archived?: boolean;
  }): Promise<ProductListResponse> => {
    const queryParams: Record<string, any> = { ...params };
    if (queryParams.include_inactive !== undefined && queryParams.is_active === undefined) {
      queryParams.is_active = !queryParams.include_inactive;
      delete queryParams.include_inactive;
    }
    if (queryParams.include_archived !== undefined && queryParams.is_archived === undefined) {
      queryParams.is_archived = queryParams.include_archived;
      delete queryParams.include_archived;
    }
    const response = await apiClient.get<ProductListResponse>('/products', { params: queryParams });
    return response.data;
  },

  getProductById: async (id: string): Promise<Product> => {
    const response = await apiClient.get<Product>(`/products/${id}`);
    return response.data;
  },

  createProduct: async (payload: ProductCreatePayload): Promise<Product> => {
    const response = await apiClient.post<Product>('/products', payload);
    return response.data;
  },

  updateProduct: async (id: string, payload: Partial<ProductCreatePayload>): Promise<Product> => {
    const response = await apiClient.patch<Product>(`/products/${id}`, payload);
    return response.data;
  },

  deleteProduct: async (id: string): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/products/${id}`);
    return response.data;
  },

  archiveProduct: async (id: string): Promise<Product> => {
    const response = await apiClient.post<Product>(`/products/${id}/archive`);
    return response.data;
  },

  restoreProduct: async (id: string): Promise<Product> => {
    const response = await apiClient.post<Product>(`/products/${id}/restore`);
    return response.data;
  },

  getCategories: async (): Promise<Category[]> => {
    const response = await apiClient.get<Category[]>('/categories');
    return response.data;
  },

  createCategory: async (payload: { name: string; description?: string }): Promise<Category> => {
    const response = await apiClient.post<Category>('/categories', payload);
    return response.data;
  },

  updateCategory: async (id: string, payload: { name?: string; description?: string }): Promise<Category> => {
    const response = await apiClient.patch<Category>(`/categories/${id}`, payload);
    return response.data;
  },

  deleteCategory: async (id: string): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/categories/${id}`);
    return response.data;
  },

  getSubcategories: async (categoryId?: string): Promise<Subcategory[]> => {
    const response = await apiClient.get<Subcategory[]>('/subcategories', {
      params: categoryId ? { category_id: categoryId } : undefined,
    });
    return response.data;
  },

  createSubcategory: async (payload: {
    category_id: string;
    name: string;
    description?: string;
  }): Promise<Subcategory> => {
    const response = await apiClient.post<Subcategory>('/subcategories', payload);
    return response.data;
  },

  addVariant: async (
    productId: string,
    payload: {
      size: string;
      color: string;
      sku: string;
      barcode?: string;
      price_override?: number;
      initial_stock: number;
      low_stock_threshold: number;
      is_active?: boolean;
    }
  ): Promise<ProductVariant> => {
    const response = await apiClient.post<ProductVariant>(`/products/${productId}/variants`, payload);
    return response.data;
  },

  updateVariant: async (
    variantId: string,
    payload: {
      size?: string;
      color?: string;
      sku?: string;
      barcode?: string;
      price_override?: number;
      is_active?: boolean;
    }
  ): Promise<ProductVariant> => {
    const response = await apiClient.patch<ProductVariant>(`/variants/${variantId}`, payload);
    return response.data;
  },

  deleteVariant: async (variantId: string): Promise<void> => {
    await apiClient.delete(`/variants/${variantId}`);
  },
};
