import React, { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Store, Loader2 } from 'lucide-react';
import { useAuthStore } from '../../stores/useAuthStore';
import { UserRole } from '../../types';
import { isTokenExpired } from '../../utils/token';

interface ProtectedRouteProps {
  children: React.ReactElement;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const { isAuthenticated, isInitializing, role, token, initializeAuth } =
    useAuthStore();
  const location = useLocation();

  useEffect(() => {
    // If store is still initializing on first mount, run initializeAuth
    if (isInitializing) {
      initializeAuth();
    }
  }, [isInitializing, initializeAuth]);

  // Loading guard: display elegant non-flashing session check
  if (isInitializing) {
    return (
      <div className="flex min-h-screen w-full flex-col items-center justify-center bg-zinc-950 p-4">
        <div className="relative flex flex-col items-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 text-zinc-950 shadow-lg shadow-amber-500/20 mb-3 animate-pulse">
            <Store className="h-6 w-6 stroke-[2.2]" />
          </div>
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-amber-400" />
            <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">
              VIYON POS
            </span>
          </div>
          <p className="mt-1 text-[11px] text-zinc-400">Verifying secure session...</p>
        </div>
      </div>
    );
  }

  // Not authenticated or token expired: redirect cleanly to login with return path
  if (!isAuthenticated || isTokenExpired(token)) {
    const currentUrl = location.pathname + location.search;
    const returnParam = encodeURIComponent(currentUrl);
    return (
      <Navigate
        to={`/login?session_expired=true&returnUrl=${returnParam}`}
        state={{ from: location }}
        replace
      />
    );
  }

  // Role verification guard
  if (allowedRoles && allowedRoles.length > 0) {
    const effectiveRole = role || 'STAFF';
    const isAllowed = allowedRoles.includes(effectiveRole);

    if (!isAllowed) {
      // If staff tries to access owner pages, redirect them to pos
      if (effectiveRole === 'STAFF') {
        return <Navigate to="/pos" replace />;
      }
      return <Navigate to="/" replace />;
    }
  }

  return children;
};
