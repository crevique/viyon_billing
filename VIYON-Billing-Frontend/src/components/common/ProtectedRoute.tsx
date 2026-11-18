import React, { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/useAuthStore';
import { UserRole } from '../../types';

interface ProtectedRouteProps {
  children: React.ReactElement;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const { isAuthenticated, role, user, fetchCurrentUser } = useAuthStore();
  const location = useLocation();

  useEffect(() => {
    if (isAuthenticated && !user) {
      fetchCurrentUser();
    }
  }, [isAuthenticated, user, fetchCurrentUser]);

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // If specific roles required, check match
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
