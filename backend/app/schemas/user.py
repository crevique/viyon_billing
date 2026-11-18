"""Pydantic schemas for authentication and user management."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator, field_validator
import re


# ------------------------------------------------------------------------------
# User Base Schemas
# ------------------------------------------------------------------------------
class UserBase(BaseModel):
    """Shared user attributes."""

    full_name: str = Field(..., min_length=2, max_length=255, description="Full name of staff or owner")
    email: Optional[EmailStr] = Field(default=None, description="Email address for login and notifications")
    username: Optional[str] = Field(default=None, min_length=3, max_length=100, description="Unique username")
    phone: Optional[str] = Field(default=None, max_length=50, description="Contact phone number")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    email: EmailStr = Field(..., description="Unique email address for login")
    password: str = Field(..., min_length=8, max_length=128, description="Plaintext password (min 8 chars)")
    role: str = Field(default="STAFF", description="Role: OWNER or STAFF")


class OwnerSetupRequest(BaseModel):
    """Schema for initial one-time store owner account creation."""

    full_name: str = Field(..., min_length=2, max_length=255, description="Full name of owner")
    email: EmailStr = Field(..., description="Unique owner email address")
    password: str = Field(..., min_length=8, max_length=128, description="Secure owner password (min 8 chars)")


class StaffCreate(BaseModel):
    """Schema for owner creating a staff account."""

    full_name: str = Field(..., min_length=2, max_length=255, description="Staff full name")
    username: Optional[str] = Field(default=None, min_length=3, max_length=100, description="Unique username for cashier login")
    email: Optional[EmailStr] = Field(default=None, description="Optional email address")
    phone: Optional[str] = Field(default=None, max_length=50, description="Optional phone number")
    password: str = Field(..., min_length=8, max_length=128, description="Initial staff password (min 8 chars)")
    confirm_password: Optional[str] = Field(default=None, min_length=8, max_length=128, description="Password confirmation")
    role: str = Field(default="STAFF", description="Role: STAFF only")

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            clean = v.strip().lower()
            return clean if clean else None
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def sanitize_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            clean = v.strip()
            return clean if clean else None
        return v

    @field_validator("username", mode="before")
    @classmethod
    def sanitize_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            clean = v.strip().lower()
            return clean if clean else None
        return v

    @model_validator(mode="after")
    def validate_staff_creation(self) -> "StaffCreate":
        # 1. Enforce STAFF role only (never allow OWNER / ADMIN)
        cleaned_role = (self.role or "").strip().upper()
        if cleaned_role != "STAFF":
            raise ValueError("Only the 'STAFF' role can be assigned through staff creation.")
        self.role = "STAFF"

        # 2. Confirm password match if provided
        if self.confirm_password is not None and self.confirm_password != self.password:
            raise ValueError("Password and confirmation password do not match.")

        # 3. Handle email-like username or standard username format
        if self.username:
            clean_u = self.username.strip().lower()
            # If user typed an email into username field (e.g. cashier@viyon.store or staff@example.com)
            if "@" in clean_u:
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_u):
                    raise ValueError("Username contains an invalid email format.")
                # If email was not explicitly provided, use the entered email
                if not self.email:
                    self.email = clean_u
                # Extract the base username part before the @
                clean_u = clean_u.split("@")[0].strip().lower()

            if not re.match(r"^[a-zA-Z0-9_.-]+$", clean_u):
                raise ValueError("Username may only contain letters, numbers, hyphens, dots, and underscores.")
            self.username = clean_u
            if not self.email:
                self.email = f"{clean_u}@viyon.store"

        if not self.username and self.email:
            self.username = self.email.split("@")[0].strip().lower()

        # Ensure either username or email is provided
        if not self.username and not self.email:
            raise ValueError("Either a unique username or a valid email address must be provided.")

        # 4. Validate phone format if provided
        if self.phone:
            clean_p = re.sub(r"[\s\-\(\)\+]", "", self.phone.strip())
            if not clean_p.isdigit() or len(clean_p) < 7 or len(clean_p) > 15:
                raise ValueError("Phone number must contain between 7 and 15 digits.")
            self.phone = clean_p

        return self


class StaffUpdate(BaseModel):
    """Schema for updating staff profile details."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None

    @field_validator("email", mode="before")
    @classmethod
    def sanitize_update_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            clean = v.strip().lower()
            return clean if clean else None
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def sanitize_update_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            clean = v.strip()
            return clean if clean else None
        return v

    @model_validator(mode="after")
    def validate_phone(self) -> "StaffUpdate":
        if self.phone:
            clean_p = re.sub(r"[\s\-\(\)\+]", "", self.phone.strip())
            if not clean_p.isdigit() or len(clean_p) < 7 or len(clean_p) > 15:
                raise ValueError("Phone number must contain between 7 and 15 digits.")
            self.phone = clean_p
        return self


class LogoutResponse(BaseModel):
    """Response confirming token invalidation on logout."""

    message: str = "Successfully logged out."
    revoked: bool = True
    timestamp: datetime


class UserUpdate(BaseModel):
    """Schema for updating user details."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None


class UserStatusUpdate(BaseModel):
    """Schema for activating or deactivating a staff account."""

    is_active: bool = Field(..., description="Set active status for the account")
    reason: Optional[str] = Field(default=None, max_length=500, description="Optional reason for status change")


class UserPasswordChange(BaseModel):
    """Schema for a user changing their own password."""

    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminPasswordReset(BaseModel):
    """Schema for owner resetting a staff member's password."""

    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: Optional[str] = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def check_match(self) -> "AdminPasswordReset":
        if self.confirm_password is not None and self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation password do not match.")
        return self


class UserOut(BaseModel):
    """Public user response schema (excluding password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: Optional[str] = None
    full_name: str
    username: Optional[str] = None
    email: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def compute_employee_id(self) -> "UserOut":
        if not self.employee_id:
            self.employee_id = f"EMP-{str(self.id)[:6].upper()}"
        return self


class StaffMetricsOut(BaseModel):
    """Staff dashboard overview summary metrics."""

    total_staff: int = 0
    active_staff: int = 0
    inactive_staff: int = 0
    created_this_month: int = 0


class StaffActivityBill(BaseModel):
    """Recent bill line in staff activity feed."""

    id: UUID
    bill_number: str
    created_at: datetime
    total_amount: Decimal
    amount_paid: Decimal
    balance_amount: Decimal
    payment_status: str
    bill_status: str
    is_cancelled: bool


class StaffActivityOut(BaseModel):
    """Comprehensive staff activity report."""

    staff_id: UUID
    employee_id: str
    full_name: str
    username: Optional[str]
    email: str
    phone: Optional[str]
    role: str
    is_active: bool
    date_joined: datetime
    last_login_at: Optional[datetime]
    total_bills_count: int
    completed_bills_count: int
    cancelled_bills_count: int
    confirmed_sales_total: Decimal
    recent_bills: List[StaffActivityBill]


# ------------------------------------------------------------------------------
# Authentication & Token Schemas
# ------------------------------------------------------------------------------
class LoginRequest(BaseModel):
    """JSON login request payload (supports email or username)."""

    email: Optional[str] = Field(default=None, description="Email address or username")
    username: Optional[str] = Field(default=None, description="Username (alternative to email)")
    password: str = Field(..., description="Account password")

    @model_validator(mode="after")
    def ensure_identifier(self) -> "LoginRequest":
        if not self.email and not self.username:
            raise ValueError("Please provide an email or username.")
        return self


class Token(BaseModel):
    """JWT access token response schema."""

    access_token: str
    token_type: str = "bearer"
    role: str
    user: UserOut


class TokenPayload(BaseModel):
    """Decoded JWT payload attributes."""

    sub: str
    role: str
    exp: int
