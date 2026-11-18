import { apiClient } from './api';
import {
  StaffActivity,
  StaffCreatePayload,
  StaffMetrics,
  StaffUpdatePayload,
  User,
} from '../types';

export const staffService = {
  getMetrics: async (): Promise<StaffMetrics> => {
    const response = await apiClient.get<StaffMetrics>('/staff/metrics');
    return response.data;
  },

  listStaff: async (params?: {
    search?: string;
    is_active?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<User[]> => {
    const response = await apiClient.get<User[]>('/staff', { params });
    return response.data;
  },

  getStaffById: async (id: string): Promise<User> => {
    const response = await apiClient.get<User>(`/staff/${id}`);
    return response.data;
  },

  createStaff: async (payload: StaffCreatePayload): Promise<User> => {
    const response = await apiClient.post<User>('/staff', payload);
    return response.data;
  },

  updateStaff: async (id: string, payload: StaffUpdatePayload): Promise<User> => {
    const response = await apiClient.patch<User>(`/staff/${id}`, payload);
    return response.data;
  },

  activateStaff: async (id: string, reason?: string): Promise<User> => {
    const response = await apiClient.patch<User>(`/staff/${id}/activate`, {
      is_active: true,
      reason,
    });
    return response.data;
  },

  deactivateStaff: async (id: string, reason?: string): Promise<User> => {
    const response = await apiClient.patch<User>(`/staff/${id}/deactivate`, {
      is_active: false,
      reason,
    });
    return response.data;
  },

  resetPassword: async (id: string, newPassword: string): Promise<User> => {
    const response = await apiClient.post<User>(`/staff/${id}/reset-password`, {
      new_password: newPassword,
      confirm_password: newPassword,
    });
    return response.data;
  },

  getActivity: async (id: string): Promise<StaffActivity> => {
    const response = await apiClient.get<StaffActivity>(`/staff/${id}/activity`);
    return response.data;
  },

  removeStaff: async (id: string): Promise<{ message: string; soft_deleted?: boolean }> => {
    const response = await apiClient.delete<{ message: string; soft_deleted?: boolean }>(`/staff/${id}`);
    return response.data;
  },
};
