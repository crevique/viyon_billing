import axios, { AxiosError } from 'axios';
import { useAuthStore, AUTH_STORAGE_KEYS } from '../stores/useAuthStore';
import { isTokenExpired } from '../utils/token';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

// Mutex / debounce guard to prevent duplicate 401 redirects and duplicate notifications
let isHandling401 = false;

// Request interceptor: attach valid token or preemptively intercept expired tokens
apiClient.interceptors.request.use(
  (config) => {
    const isAuthRoute =
      config.url?.includes('/auth/login') ||
      config.url?.includes('/auth/setup-owner');

    if (isAuthRoute) {
      return config;
    }

    const token = localStorage.getItem(AUTH_STORAGE_KEYS.TOKEN);

    if (token) {
      // Check if token has already expired before sending request
      if (isTokenExpired(token)) {
        if (!isHandling401) {
          isHandling401 = true;
          useAuthStore.getState().expireSession();
          setTimeout(() => {
            isHandling401 = false;
          }, 2000);
        }
        return Promise.reject(
          new axios.Cancel('Session expired. Redirecting to login...')
        );
      }

      if (config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle 401 session expiry and prevent duplicate redirects
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Check if error was a cancelled request
    if (axios.isCancel(error)) {
      return Promise.reject(error);
    }

    const status = error.response?.status;
    const requestUrl = error.config?.url || '';

    // Handle 401 Unauthorized
    if (status === 401) {
      const isLoginOrAuthAttempt =
        requestUrl.includes('/auth/login') ||
        requestUrl.includes('/auth/setup-owner');

      // Do NOT redirect or clear session when login credentials are wrong
      if (!isLoginOrAuthAttempt) {
        if (!isHandling401) {
          isHandling401 = true;
          useAuthStore.getState().expireSession();
          setTimeout(() => {
            isHandling401 = false;
          }, 2000);
        }
      }
    }

    // Notice: 403 Forbidden is strictly treated as access-denied, NOT session expiry
    // Notice: 5xx, 502, 503, 504 and network errors are passed through without logout

    return Promise.reject(error);
  }
);

export function getErrorMessage(error: unknown): string {
  if (axios.isCancel(error)) {
    return error.message || 'Request cancelled.';
  }

  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (data) {
      if (typeof data === 'string') return data;
      if (data.detail) {
        if (typeof data.detail === 'string') return data.detail;
        if (Array.isArray(data.detail) && data.detail.length > 0) {
          // Pydantic validation error array
          return data.detail.map((e: any) => e.msg || e.message).join(', ');
        }
      }
      if (data.message) return data.message;
    }
    if (error.message) return error.message;
  }
  return error instanceof Error ? error.message : 'An unexpected error occurred.';
}
