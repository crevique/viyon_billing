"""Token revocation blacklist mechanism for secure JWT logout and user session invalidation."""

import time
import hashlib
from threading import Lock
from typing import Dict, Optional, Union
from uuid import UUID


class TokenBlacklist:
    """Thread-safe in-memory store for revoked JWT tokens and user session invalidations."""

    def __init__(self):
        # Maps SHA256(token) -> expiration_timestamp
        self._revoked_tokens: Dict[str, float] = {}
        # Maps str(user_id) -> revocation_cutoff_timestamp
        self._revoked_users: Dict[str, float] = {}
        self._lock = Lock()

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def revoke(self, token: str, exp_timestamp: float) -> None:
        """Mark an individual token as revoked until its original expiration timestamp."""
        token_hash = self._hash_token(token)
        now = time.time()
        with self._lock:
            # Purge any already expired tokens to prevent memory growth
            self._revoked_tokens = {
                h: exp for h, exp in self._revoked_tokens.items() if exp > now
            }
            if exp_timestamp > now:
                self._revoked_tokens[token_hash] = exp_timestamp

    def revoke_user_sessions(self, user_id: Union[str, UUID]) -> None:
        """Revoke all tokens issued for a user before this moment (e.g. on password reset or deactivation)."""
        now = time.time()
        with self._lock:
            self._revoked_users[str(user_id)] = now

    def is_revoked(self, token: str) -> bool:
        """Check if an individual token has been revoked."""
        token_hash = self._hash_token(token)
        now = time.time()
        with self._lock:
            exp = self._revoked_tokens.get(token_hash)
            if exp is None:
                return False
            if exp <= now:
                del self._revoked_tokens[token_hash]
                return False
            return True

    def is_user_session_revoked(
        self,
        user_id: Union[str, UUID],
        token_iat: Optional[Union[float, int]],
    ) -> bool:
        """Check if a token was issued before the user session revocation cutoff."""
        with self._lock:
            cutoff = self._revoked_users.get(str(user_id))
            if cutoff is None:
                return False
            if token_iat is None:
                return True
            return float(token_iat) <= cutoff

    def clear(self) -> None:
        """Clear all blacklists (useful for testing)."""
        with self._lock:
            self._revoked_tokens.clear()
            self._revoked_users.clear()


token_blacklist = TokenBlacklist()
