"""Authentication API endpoints for staff and owner login, setup, and session management."""

import hashlib
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, oauth2_scheme
from app.core.config import settings
from app.core.rate_limit import login_rate_limiter
from app.core.security import create_access_token, decode_access_token
from app.core.token_blacklist import token_blacklist
from app.database.connection import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.user import (
    LoginRequest,
    LogoutResponse,
    OwnerSetupRequest,
    Token,
    UserOut,
    UserPasswordChange,
)
from app.services.auth_service import AuthService

router = APIRouter()


# ------------------------------------------------------------------------------
# 1. Initial One-Time Owner Setup
# ------------------------------------------------------------------------------
@router.post(
    "/setup-owner",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="One-Time Store Owner Setup",
    description=(
        "Initialize the store owner account. Strictly one-time operation. "
        "Requires secret X-Setup-Token header matching server configuration. "
        "Disabled permanently once an OWNER account exists."
    ),
)
def setup_initial_owner(
    owner_in: OwnerSetupRequest,
    x_setup_token: Optional[str] = Header(None, alias="X-Setup-Token"),
    db: Session = Depends(get_db),
) -> UserOut:
    """Securely create the initial store owner account."""
    # Verify setup token
    if not x_setup_token or x_setup_token != settings.OWNER_SETUP_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing owner setup token.",
        )

    # Verify no owner exists before processing
    if AuthService.has_owner(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: A store owner account already exists. One-time setup is disabled.",
        )

    try:
        owner = AuthService.setup_initial_owner(db, owner_in)
        return UserOut.model_validate(owner)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ------------------------------------------------------------------------------
# 2. Login Endpoints (Form and JSON)
# ------------------------------------------------------------------------------
def _process_login(identifier: str, password: str, request: Request, db: Session) -> Token:
    """Internal shared login routine with brute-force rate-limiting and audit logging."""
    client_ip = request.client.host if request.client else "unknown"
    normalized_id = identifier.strip().lower()

    # Enforce brute-force protection
    login_rate_limiter.check_rate_limit(client_ip)
    login_rate_limiter.check_rate_limit(normalized_id)

    user = AuthService.authenticate(db, identifier=normalized_id, password=password)
    now_utc = datetime.now(timezone.utc)

    if not user:
        login_rate_limiter.record_failed_attempt(client_ip)
        login_rate_limiter.record_failed_attempt(normalized_id)

        # Audit failed login attempt if account exists
        target = AuthService.get_by_identifier(db, normalized_id)
        if target:
            action_name = "OWNER_LOGIN_FAILED" if target.role == "OWNER" else "STAFF_LOGIN_FAILED"
            audit = AuditLog(
                id=uuid4(),
                user_id=target.id,
                action=action_name,
                entity_type="USER",
                entity_id=target.id,
                new_values={"identifier": normalized_id, "reason": "Incorrect password"},
                ip_address=client_ip,
                created_at=now_utc,
            )
            db.add(audit)
            db.commit()

        # Generic authentication failure: never reveal if email/username exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        # Inactive user check
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Please contact store management.",
        )

    # Clear rate limit trackers upon successful login
    login_rate_limiter.clear(client_ip)
    login_rate_limiter.clear(normalized_id)

    # Update last login time and record audit log
    user.last_login_at = now_utc
    db.add(user)

    login_action = "OWNER_LOGIN" if user.role == "OWNER" else "STAFF_LOGIN"
    audit = AuditLog(
        id=uuid4(),
        user_id=user.id,
        action=login_action,
        entity_type="USER",
        entity_id=user.id,
        new_values={"role": user.role, "timestamp": now_utc.isoformat()},
        ip_address=client_ip,
        created_at=now_utc,
    )
    db.add(audit)
    db.commit()
    db.refresh(user)

    pwd_v = hashlib.sha256(user.password_hash.encode("utf-8")).hexdigest()[:16]
    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        extra_claims={"pwd_v": pwd_v},
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/login",
    response_model=Token,
    summary="User Login (OAuth2 Form Compatible)",
    description="Authenticate with email or username and password. Compatible with Swagger UI Authorize dialog.",
)
def login_form(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """OAuth2 password form login."""
    return _process_login(form_data.username, form_data.password, request, db)


@router.post(
    "/login/json",
    response_model=Token,
    summary="User Login (JSON Body)",
    description="Authenticate with JSON body containing email or username and password. Designed for single-page applications.",
)
def login_json(
    request: Request,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
) -> Token:
    """JSON body login."""
    identifier = credentials.email or credentials.username or ""
    return _process_login(identifier, credentials.password, request, db)


# ------------------------------------------------------------------------------
# 3. Current User Profile
# ------------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserOut,
    summary="Get Current Authenticated User",
    description="Retrieve the profile of the currently logged-in user. Requires valid Bearer JWT.",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    """Return verified user profile excluding password hash."""
    return UserOut.model_validate(current_user)


# ------------------------------------------------------------------------------
# 4. Logout (Server-Side Revocation)
# ------------------------------------------------------------------------------
@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="User Logout",
    description="Revoke the current Bearer JWT token on the server and terminate the session.",
)
def logout(
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
) -> LogoutResponse:
    """Invalidate current access token in the server-side revocation list."""
    try:
        payload = decode_access_token(token)
        exp_timestamp = payload.get("exp", 0)
    except Exception:
        exp_timestamp = 0

    token_blacklist.revoke(token, exp_timestamp)
    return LogoutResponse(
        message="Successfully logged out. Token has been revoked.",
        revoked=True,
        timestamp=datetime.now(timezone.utc),
    )


# ------------------------------------------------------------------------------
# 5. Password Management
# ------------------------------------------------------------------------------
@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change Own Password",
    description="Update the password of the currently authenticated user.",
)
def change_own_password(
    data: UserPasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify current password and set new password."""
    success = AuthService.change_password(
        db,
        user=current_user,
        current_password=data.current_password,
        new_password=data.new_password,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password.",
        )
    return {"message": "Password changed successfully."}
