/**
 * JWT Token Utilities for VIYON Billing POS
 * Safe client-side payload inspection and expiration calculations.
 */

export interface JwtPayload {
  sub?: string;
  role?: string;
  exp?: number;
  iat?: number;
  pwd_v?: string;
  [key: string]: unknown;
}

/**
 * Safely parse a JWT payload without external libraries.
 */
export function parseJwtPayload(token: string | null | undefined): JwtPayload | null {
  if (!token || typeof token !== 'string') return null;
  try {
    const parts = token.trim().split('.');
    if (parts.length !== 3) return null;
    const base64Url = parts[1];
    if (!base64Url) return null;

    let base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4 !== 0) {
      base64 += '=';
    }

    const decoded = atob(base64);
    const jsonStr = decodeURIComponent(
      decoded
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonStr) as JwtPayload;
  } catch {
    return null;
  }
}

/**
 * Check if the given JWT token is expired or close to expiring (within bufferSeconds).
 * Default buffer is 30 seconds to prevent inflight requests from failing due to race conditions.
 */
export function isTokenExpired(token: string | null | undefined, bufferSeconds = 30): boolean {
  if (!token) return true;
  const payload = parseJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return true;
  const nowInSeconds = Math.floor(Date.now() / 1000);
  return payload.exp <= nowInSeconds + bufferSeconds;
}

/**
 * Calculate the remaining lifetime of the token in milliseconds.
 * Returns 0 if expired or invalid.
 */
export function getTokenRemainingTimeMs(token: string | null | undefined): number {
  if (!token) return 0;
  const payload = parseJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return 0;
  const remainingMs = payload.exp * 1000 - Date.now();
  return Math.max(0, remainingMs);
}

/**
 * Get the exact Expiration Date of the token.
 */
export function getTokenExpiryDate(token: string | null | undefined): Date | null {
  if (!token) return null;
  const payload = parseJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return null;
  return new Date(payload.exp * 1000);
}
