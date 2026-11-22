import React, { useEffect } from 'react';
import { BrowserRouter, useNavigate, useLocation } from 'react-router-dom';
import { AppRoutes } from './routes/AppRoutes';
import { useAuthStore, AUTH_STORAGE_KEYS } from './stores/useAuthStore';
import { isTokenExpired } from './utils/token';

const AuthSessionManager: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { initializeAuth, logout, expireSession, isAuthenticated, token } = useAuthStore();

  // Initialize auth state on application startup
  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  // Synchronize across browser tabs and handle background tab resumes
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      // 1. Cross-tab auth events
      if (e.key === AUTH_STORAGE_KEYS.AUTH_EVENT && e.newValue) {
        try {
          const eventData = JSON.parse(e.newValue);
          if (eventData.type === 'LOGOUT') {
            logout(false);
            if (location.pathname !== '/login') {
              navigate('/login?session_expired=true', { replace: true });
            }
          } else if (eventData.type === 'LOGIN') {
            initializeAuth();
          }
        } catch {
          // Ignore parse errors
        }
      }

      // 2. Direct removal of token from storage in another tab
      if (e.key === AUTH_STORAGE_KEYS.TOKEN && !e.newValue) {
        logout(false);
        if (location.pathname !== '/login') {
          navigate('/login?session_expired=true', { replace: true });
        }
      }
    };

    // 3. Tab visibility / focus resume checks (e.g., returning to open tab after hours)
    const handleVisibilityOrFocus = () => {
      if (document.visibilityState === 'visible' && isAuthenticated) {
        const currentToken = localStorage.getItem(AUTH_STORAGE_KEYS.TOKEN);
        if (!currentToken || isTokenExpired(currentToken)) {
          expireSession('Your session has expired while away. Please sign in again.');
        }
      }
    };

    window.addEventListener('storage', handleStorageChange);
    document.addEventListener('visibilitychange', handleVisibilityOrFocus);
    window.addEventListener('focus', handleVisibilityOrFocus);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      document.removeEventListener('visibilitychange', handleVisibilityOrFocus);
      window.removeEventListener('focus', handleVisibilityOrFocus);
    };
  }, [initializeAuth, logout, expireSession, isAuthenticated, location.pathname, navigate]);

  return <>{children}</>;
};

export function App() {
  return (
    <BrowserRouter>
      <AuthSessionManager>
        <AppRoutes />
      </AuthSessionManager>
    </BrowserRouter>
  );
}

export default App;
