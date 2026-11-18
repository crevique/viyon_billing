"""Common API dependencies, security guards, and database session injection."""

import hashlib
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.core.token_blacklist import token_blacklist
from app.database.connection import get_db
from app.models.user import User
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=True,
)


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """Validate JWT bearer token, check revocation, and retrieve active user."""
    # Check if token was explicitly revoked via logout
    if token_blacklist.is_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id_raw = payload.get("sub")
        if not user_id_raw or not isinstance(user_id_raw, str):
            raise credentials_exception
        user_id = UUID(user_id_raw)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    user = AuthService.get_by_id(db, user_id)
    if not user:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your user account is inactive. Please contact the store owner.",
        )

    # Invalidate session if password was changed since token issuance
    token_pwd_v = payload.get("pwd_v")
    if token_pwd_v:
        current_pwd_v = hashlib.sha256(user.password_hash.encode("utf-8")).hexdigest()[:16]
        if token_pwd_v != current_pwd_v:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Password was changed. Please log in again with your new credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # Fallback for legacy tokens without pwd_v claim: check user session revocation timestamp
        token_iat = payload.get("iat")
        if token_blacklist.is_user_session_revoked(user.id, token_iat):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token session has been invalidated. Please log in again with your new credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return user


def require_owner(
    current_user: User = Depends(get_current_user),
) -> User:
    """Security dependency ensuring the requesting user has verified OWNER role in database."""
    if current_user.role != "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Store owner privileges required.",
        )
    return current_user


def require_staff_or_owner(
    current_user: User = Depends(get_current_user),
) -> User:
    """Security dependency ensuring the user is an active store employee or owner."""
    if current_user.role not in ("OWNER", "STAFF"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Valid store staff or owner role required.",
        )
    return current_user


# Alias for backward compatibility
require_active_staff = require_staff_or_owner
