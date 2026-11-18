import { apiClient } from './api';
import { LoginPayload, TokenResponse, User } from '../types';

export const authService = {
  login: async (payload: LoginPayload): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>('/auth/login/json', payload);
    return response.data;
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      // Ignore network or logout failure during local logout
    } finally {
      localStorage.removeItem('viyon_auth_token');
      localStorage.removeItem('viyon_user_role');
      localStorage.removeItem('viyon_user_profile');
    }
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<{ message: string }> => {
    const response = await apiClient.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  },
};
