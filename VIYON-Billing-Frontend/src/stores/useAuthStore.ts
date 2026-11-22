import { create } from 'zustand';
import { User, UserRole, LoginPayload } from '../types';
import { authService } from '../services/authService';
import { getErrorMessage } from '../services/api';
import {
  isTokenExpired,
  getTokenRemainingTimeMs,
} from '../utils/token';

export const AUTH_STORAGE_KEYS = {
  TOKEN: 'viyon_auth_token',
  ROLE: 'viyon_user_role',
  PROFILE: 'viyon_user_profile',
  AUTH_EVENT: 'viyon_auth_event',
  RETURN_URL: 'viyon_return_url',
} as const;

interface AuthState {
  token: string | null;
  user: User | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  isLoading: boolean;
  error: string | null;
  sessionExpiredNotice: string | null;

  initializeAuth: () => Promise<void>;
  login: (payload: LoginPayload) => Promise<User>;
  logout: (notifyServer?: boolean) => Promise<void>;
  expireSession: (message?: string) => void;
  fetchCurrentUser: () => Promise<void>;
  clearError: () => void;
  clearSessionExpiredNotice: () => void;
}

const getStoredToken = () => localStorage.getItem(AUTH_STORAGE_KEYS.TOKEN);
const getStoredUser = (): User | null => {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEYS.PROFILE);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};
const getStoredRole = (): UserRole | null => {
  const role = localStorage.getItem(AUTH_STORAGE_KEYS.ROLE);
  return (role as UserRole) || null;
};

const clearStoredAuth = () => {
  localStorage.removeItem(AUTH_STORAGE_KEYS.TOKEN);
  localStorage.removeItem(AUTH_STORAGE_KEYS.ROLE);
  localStorage.removeItem(AUTH_STORAGE_KEYS.PROFILE);
};

// Global timer reference for proactive session expiry
let proactiveExpiryTimer: ReturnType<typeof setTimeout> | null = null;

const scheduleProactiveExpiry = (token: string | null) => {
  if (proactiveExpiryTimer) {
    clearTimeout(proactiveExpiryTimer);
    proactiveExpiryTimer = null;
  }

  if (!token) return;

  const remainingMs = getTokenRemainingTimeMs(token);
  if (remainingMs <= 0) {
    useAuthStore.getState().expireSession();
    return;
  }

  // Fire proactive expiry 5 seconds before token hard expiration or when remainingMs arrives
  const fireDelay = Math.max(1000, remainingMs - 5000);
  proactiveExpiryTimer = setTimeout(() => {
    useAuthStore.getState().expireSession();
  }, fireDelay);
};

const clearProactiveExpiry = () => {
  if (proactiveExpiryTimer) {
    clearTimeout(proactiveExpiryTimer);
    proactiveExpiryTimer = null;
  }
};

// Check initial stored token validity on module load
const initialToken = getStoredToken();
const isInitialTokenValid = initialToken ? !isTokenExpired(initialToken) : false;

if (!isInitialTokenValid && initialToken) {
  // Proactively purge stale or expired token from previous session
  clearStoredAuth();
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: isInitialTokenValid ? initialToken : null,
  user: isInitialTokenValid ? getStoredUser() : null,
  role: isInitialTokenValid ? getStoredRole() : null,
  isAuthenticated: isInitialTokenValid,
  isInitializing: isInitialTokenValid,
  isLoading: false,
  error: null,
  sessionExpiredNotice: null,

  clearError: () => set({ error: null }),
  clearSessionExpiredNotice: () => set({ sessionExpiredNotice: null }),

  initializeAuth: async () => {
    const token = getStoredToken();
    if (!token || isTokenExpired(token)) {
      clearStoredAuth();
      clearProactiveExpiry();
      set({
        token: null,
        user: null,
        role: null,
        isAuthenticated: false,
        isInitializing: false,
      });
      return;
    }

    scheduleProactiveExpiry(token);

    // Verify session with backend to get latest user status
    try {
      const user = await authService.getMe();
      localStorage.setItem(AUTH_STORAGE_KEYS.ROLE, user.role);
      localStorage.setItem(AUTH_STORAGE_KEYS.PROFILE, JSON.stringify(user));
      set({
        token,
        user,
        role: user.role,
        isAuthenticated: true,
        isInitializing: false,
      });
    } catch (err: any) {
      // If 401 Unauthorized, session is truly invalid/expired on backend
      if (err?.response?.status === 401) {
        get().expireSession();
      } else {
        // For transient network errors / cold start (5xx, ECONNREFUSED),
        // preserve the cached session so user isn't kicked out during network blips
        set({
          token,
          user: getStoredUser(),
          role: getStoredRole(),
          isAuthenticated: true,
          isInitializing: false,
        });
      }
    }
  },

  login: async (payload: LoginPayload) => {
    set({ isLoading: true, error: null, sessionExpiredNotice: null });
    try {
      const response = await authService.login(payload);
      localStorage.setItem(AUTH_STORAGE_KEYS.TOKEN, response.access_token);
      localStorage.setItem(AUTH_STORAGE_KEYS.ROLE, response.role);
      localStorage.setItem(AUTH_STORAGE_KEYS.PROFILE, JSON.stringify(response.user));

      // Broadcast login event across open tabs
      try {
        localStorage.setItem(
          AUTH_STORAGE_KEYS.AUTH_EVENT,
          JSON.stringify({ type: 'LOGIN', timestamp: Date.now() })
        );
      } catch {
        // Ignore storage event failures
      }

      scheduleProactiveExpiry(response.access_token);

      set({
        token: response.access_token,
        role: response.role,
        user: response.user,
        isAuthenticated: true,
        isInitializing: false,
        isLoading: false,
        error: null,
        sessionExpiredNotice: null,
      });

      return response.user;
    } catch (err) {
      const message = getErrorMessage(err);
      set({ error: message, isLoading: false });
      throw new Error(message);
    }
  },

  logout: async (notifyServer = true) => {
    clearProactiveExpiry();
    const token = get().token;

    // Clear local authentication state first
    clearStoredAuth();

    // Broadcast logout event across tabs
    try {
      localStorage.setItem(
        AUTH_STORAGE_KEYS.AUTH_EVENT,
        JSON.stringify({ type: 'LOGOUT', timestamp: Date.now() })
      );
    } catch {
      // Ignore storage event failures
    }

    set({
      token: null,
      user: null,
      role: null,
      isAuthenticated: false,
      isInitializing: false,
      error: null,
      sessionExpiredNotice: null,
    });

    if (notifyServer && token) {
      try {
        await authService.logout();
      } catch {
        // Ignore network or logout failure during local logout
      }
    }
  },

  expireSession: (message = 'Your session has expired. Please sign in again.') => {
    clearProactiveExpiry();

    // Capture return URL if not already on login page
    const pathname = window.location.pathname;
    const search = window.location.search;
    const currentUrl = pathname + search;

    if (pathname !== '/login') {
      try {
        sessionStorage.setItem(AUTH_STORAGE_KEYS.RETURN_URL, currentUrl);
      } catch {
        // Ignore sessionStorage errors
      }
    }

    clearStoredAuth();

    // Broadcast logout event across tabs
    try {
      localStorage.setItem(
        AUTH_STORAGE_KEYS.AUTH_EVENT,
        JSON.stringify({ type: 'LOGOUT', reason: 'expired', timestamp: Date.now() })
      );
    } catch {
      // Ignore storage errors
    }

    set({
      token: null,
      user: null,
      role: null,
      isAuthenticated: false,
      isInitializing: false,
      sessionExpiredNotice: message,
    });

    // Clean redirection to login page with preserved return URL
    if (pathname !== '/login') {
      const returnParam = encodeURIComponent(currentUrl);
      window.location.href = `/login?session_expired=true&returnUrl=${returnParam}`;
    }
  },

  fetchCurrentUser: async () => {
    const token = getStoredToken();
    if (!token || isTokenExpired(token)) {
      get().expireSession();
      return;
    }
    try {
      const user = await authService.getMe();
      localStorage.setItem(AUTH_STORAGE_KEYS.ROLE, user.role);
      localStorage.setItem(AUTH_STORAGE_KEYS.PROFILE, JSON.stringify(user));
      set({
        user,
        role: user.role,
        isAuthenticated: true,
      });
    } catch (err: any) {
      if (err?.response?.status === 401) {
        get().expireSession();
      }
    }
  },
}));

// Initialize proactive expiry timer if a valid token is currently loaded
if (isInitialTokenValid && initialToken) {
  scheduleProactiveExpiry(initialToken);
}
