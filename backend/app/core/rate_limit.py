"""Thread-safe rate limiting utility for brute-force protection."""

import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List
from fastapi import HTTPException, status
from app.core.config import settings


class LoginRateLimiter:
    """Sliding-window in-memory rate limiter for authentication endpoints."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()

    def _cleanup_expired(self, now: float, key: str) -> None:
        """Purge timestamps outside the current sliding time window."""
        cutoff = now - self.window_seconds
        self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]

    def check_rate_limit(self, identifier: str) -> None:
        """Check if an identifier (IP address or email) has exceeded the failed attempt limit."""
        now = time.time()
        with self._lock:
            self._cleanup_expired(now, identifier)
            if len(self._attempts[identifier]) >= self.max_attempts:
                oldest_attempt = self._attempts[identifier][0]
                retry_after = max(1, int(self.window_seconds - (now - oldest_attempt)) + 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed login attempts. Please wait {retry_after} seconds before trying again.",
                    headers={"Retry-After": str(retry_after)},
                )

    def record_failed_attempt(self, identifier: str) -> None:
        """Record a failed login attempt timestamp."""
        now = time.time()
        with self._lock:
            self._cleanup_expired(now, identifier)
            self._attempts[identifier].append(now)

    def clear(self, identifier: str) -> None:
        """Clear recorded failures upon successful authentication."""
        with self._lock:
            if identifier in self._attempts:
                del self._attempts[identifier]

    def reset_all(self) -> None:
        """Clear all rate limiter state (useful for automated testing)."""
        with self._lock:
            self._attempts.clear()


# Global singleton using application settings
login_rate_limiter = LoginRateLimiter(
    max_attempts=settings.RATE_LIMIT_LOGIN_ATTEMPTS,
    window_seconds=settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS,
)
