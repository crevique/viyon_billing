import { create } from 'zustand';
import { User, UserRole, LoginPayload } from '../types';
import { authService } from '../services/authService';
import { getErrorMessage } from '../services/api';

interface AuthState {
  token: string | null;
  user: User | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (payload: LoginPayload) => Promise<User>;
  logout: () => Promise<void>;
  fetchCurrentUser: () => Promise<void>;
  clearError: () => void;
}

const getStoredToken = () => localStorage.getItem('viyon_auth_token');
const getStoredUser = (): User | null => {
  try {
    const raw = localStorage.getItem('viyon_user_profile');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};
const getStoredRole = (): UserRole | null => {
  const role = localStorage.getItem('viyon_user_role');
  return (role as UserRole) || null;
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: getStoredToken(),
  user: getStoredUser(),
  role: getStoredRole(),
  isAuthenticated: !!getStoredToken(),
  isLoading: false,
  error: null,

  clearError: () => set({ error: null }),

  login: async (payload: LoginPayload) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authService.login(payload);
      localStorage.setItem('viyon_auth_token', response.access_token);
      localStorage.setItem('viyon_user_role', response.role);
      localStorage.setItem('viyon_user_profile', JSON.stringify(response.user));

      set({
        token: response.access_token,
        role: response.role,
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      return response.user;
    } catch (err) {
      const message = getErrorMessage(err);
      set({ error: message, isLoading: false });
      throw new Error(message);
    }
  },

  logout: async () => {
    try {
      await authService.logout();
    } finally {
      set({
        token: null,
        user: null,
        role: null,
        isAuthenticated: false,
        error: null,
      });
    }
  },

  fetchCurrentUser: async () => {
    if (!getStoredToken()) return;
    try {
      const user = await authService.getMe();
      localStorage.setItem('viyon_user_role', user.role);
      localStorage.setItem('viyon_user_profile', JSON.stringify(user));
      set({
        user,
        role: user.role,
        isAuthenticated: true,
      });
    } catch {
      // If token is invalid or expired
      get().logout();
    }
  },
}));
