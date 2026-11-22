import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Eye, EyeOff, Lock, User, Store, AlertCircle } from 'lucide-react';
import { useAuthStore, AUTH_STORAGE_KEYS } from '../../stores/useAuthStore';
import { UserRole } from '../../types';
import { isTokenExpired } from '../../utils/token';

function isOwnerOnlyPath(pathname: string): boolean {
  if (pathname === '/') return true;
  if (pathname === '/purchases' || pathname.startsWith('/purchases/payments')) return true;
  return (
    pathname.startsWith('/settings') ||
    pathname.startsWith('/finance') ||
    pathname.startsWith('/expenses') ||
    pathname.startsWith('/suppliers') ||
    pathname.startsWith('/staff-management') ||
    pathname.startsWith('/audit-history')
  );
}

function resolveReturnDestination(
  rawCandidate: string | null | undefined,
  userRole: UserRole
): string {
  const isOwner = userRole === 'OWNER' || userRole === 'ADMIN';

  if (!rawCandidate || typeof rawCandidate !== 'string') {
    return isOwner ? '/' : '/pos';
  }

  try {
    const decoded = decodeURIComponent(rawCandidate);
    // Security check: Must be a relative path and not a protocol or open redirect
    if (!decoded.startsWith('/') || decoded.startsWith('//') || decoded.startsWith('/login')) {
      return isOwner ? '/' : '/pos';
    }

    // Role-based route validation
    if (!isOwner) {
      const pathOnly = decoded.split('?')[0].split('#')[0];
      if (isOwnerOnlyPath(pathOnly)) {
        return '/pos';
      }
    }

    return decoded;
  } catch {
    return isOwner ? '/' : '/pos';
  }
}

export const LoginPage: React.FC = () => {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const {
    login,
    isLoading,
    error,
    isAuthenticated,
    token,
    role,
    sessionExpiredNotice,
    clearError,
    clearSessionExpiredNotice,
  } = useAuthStore();

  const navigate = useNavigate();
  const location = useLocation();

  // Determine potential return URL from query params, router state, or session storage
  const returnUrlParam = useMemo(() => {
    const queryParams = new URLSearchParams(location.search);
    const paramUrl = queryParams.get('returnUrl');
    const stateUrl = (location.state as any)?.from?.pathname
      ? (location.state as any).from.pathname + ((location.state as any).from.search || '')
      : null;
    const storedUrl = sessionStorage.getItem(AUTH_STORAGE_KEYS.RETURN_URL);

    return paramUrl || stateUrl || storedUrl || null;
  }, [location]);

  // Check if session expired from redirect param or store
  const queryParams = new URLSearchParams(location.search);
  const isSessionExpired =
    queryParams.get('session_expired') === 'true' || !!sessionExpiredNotice;

  // If already authenticated with a valid token, redirect immediately
  useEffect(() => {
    if (isAuthenticated && !isTokenExpired(token) && role) {
      const destination = resolveReturnDestination(returnUrlParam, role);
      try {
        sessionStorage.removeItem(AUTH_STORAGE_KEYS.RETURN_URL);
      } catch {
        // Ignore storage error
      }
      navigate(destination, { replace: true });
    }
  }, [isAuthenticated, token, role, returnUrlParam, navigate]);

  const handleInputChange = () => {
    if (validationError) setValidationError(null);
    if (error) clearError();
    if (sessionExpiredNotice) clearSessionExpiredNotice();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    clearError();
    clearSessionExpiredNotice();

    if (!identifier.trim()) {
      setValidationError('Please enter your email or staff username.');
      return;
    }
    if (!password) {
      setValidationError('Please enter your password.');
      return;
    }

    try {
      const user = await login({
        username: identifier.includes('@') ? undefined : identifier.trim(),
        email: identifier.includes('@') ? identifier.trim() : undefined,
        password,
      });

      const destination = resolveReturnDestination(returnUrlParam, user.role);
      try {
        sessionStorage.removeItem(AUTH_STORAGE_KEYS.RETURN_URL);
      } catch {
        // Ignore storage error
      }
      navigate(destination, { replace: true });
    } catch {
      // Handled by store
    }
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-zinc-950 p-3 sm:p-4">
      {/* Background radial gradient */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(217,155,50,0.08)_0%,transparent_70%)] pointer-events-none" />

      <div className="relative w-full max-w-md overflow-hidden rounded-2xl sm:rounded-3xl border border-zinc-800/80 bg-zinc-900/90 p-5 sm:p-8 shadow-2xl backdrop-blur-xl">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 text-zinc-950 shadow-lg shadow-amber-500/20 mb-4">
            <Store className="h-8 w-8 stroke-[2.2]" />
          </div>
          <h1 className="font-serif text-2xl font-black tracking-widest text-white">
            VIYON
          </h1>
          <p className="mt-1 text-xs font-bold uppercase tracking-widest text-amber-400">
            STORE MANAGEMENT & POINT OF SALE
          </p>
          <p className="mt-1 text-[11px] text-zinc-500">
            Sathyamangalam, Tamil Nadu • 082702 42681
          </p>
        </div>

        {/* Expired Session Notice */}
        {isSessionExpired && (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-amber-400" />
            <span>
              {sessionExpiredNotice || 'Your session has expired. Please sign in again to continue.'}
            </span>
          </div>
        )}

        {/* Validation or API Errors */}
        {(validationError || error) && (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{validationError || error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
              Username or Email
            </label>
            <div className="relative">
              <User className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                autoComplete="username"
                placeholder="e.g. owner@viyon.store or staff_cashier"
                value={identifier}
                onChange={(e) => {
                  setIdentifier(e.target.value);
                  handleInputChange();
                }}
                disabled={isLoading}
                className="w-full rounded-xl border border-zinc-700/80 bg-zinc-800/80 pl-10 pr-4 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:border-amber-400 focus:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-amber-400 disabled:opacity-50"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <input
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                placeholder="Enter password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  handleInputChange();
                }}
                disabled={isLoading}
                className="w-full rounded-xl border border-zinc-700/80 bg-zinc-800/80 pl-10 pr-10 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:border-amber-400 focus:bg-zinc-800 focus:outline-none focus:ring-1 focus:ring-amber-400 disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-2 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-400 to-amber-500 py-3 text-xs font-bold text-zinc-950 shadow-lg shadow-amber-500/20 transition-all hover:from-amber-300 hover:to-amber-400 active:scale-98 disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-950 border-t-transparent" />
                <span>Authenticating...</span>
              </>
            ) : (
              <span>Sign In to POS</span>
            )}
          </button>
        </form>

        <div className="mt-8 border-t border-zinc-800/80 pt-4 text-center">
          <p className="text-[11px] text-zinc-500">
            VIYON Retail Management System • Internal Access Only
          </p>
        </div>
      </div>
    </div>
  );
};
