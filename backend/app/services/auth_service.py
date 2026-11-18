"""Authentication and user management business logic."""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, func, text, or_
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import StaffCreate, OwnerSetupRequest


class AuthService:
    """Service providing user authentication, credential verification, and staff administration."""

    @classmethod
    def has_owner(cls, db: Session) -> bool:
        """Check whether an OWNER account already exists."""
        count = db.scalar(select(func.count(User.id)).where(User.role == "OWNER"))
        return (count or 0) > 0

    @classmethod
    def setup_initial_owner(cls, db: Session, owner_in: OwnerSetupRequest) -> User:
        """Create the initial store owner account. Strictly one-time operation."""
        # Acquire transaction-level advisory lock on PostgreSQL to prevent concurrent setup race conditions
        bind = db.get_bind()
        if bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(847392);"))

        # Verify under lock that no owner exists
        if cls.has_owner(db):
            raise ValueError("Store owner account already exists. One-time setup is disabled.")

        email = owner_in.email.strip().lower()
        existing = cls.get_by_email(db, email)
        if existing:
            raise ValueError(f"An account with email '{email}' already exists.")

        owner = User(
            full_name=owner_in.full_name.strip(),
            username=email.split("@")[0].strip().lower(),
            email=email,
            password_hash=get_password_hash(owner_in.password),
            role="OWNER",
            is_active=True,
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)
        return owner

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        """Fetch a user by normalized email address."""
        return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))

    @staticmethod
    def get_by_identifier(db: Session, identifier: str) -> Optional[User]:
        """Fetch a user by either email or username."""
        clean_id = identifier.strip().lower()
        return db.scalar(
            select(User).where(
                or_(
                    func.lower(User.email) == clean_id,
                    func.lower(User.username) == clean_id,
                )
            )
        )

    @staticmethod
    def get_by_id(db: Session, user_id: UUID) -> Optional[User]:
        """Fetch a user by unique identifier."""
        return db.scalar(select(User).where(User.id == user_id))

    @classmethod
    def authenticate(cls, db: Session, identifier: str, password: str, email: Optional[str] = None) -> Optional[User]:
        """Authenticate user by identifier (email or username) and password, returning User if valid."""
        lookup_key = identifier if identifier else (email or "")
        user = cls.get_by_identifier(db, lookup_key)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @classmethod
    def create_staff(cls, db: Session, staff_in: StaffCreate) -> User:
        """Create a new staff account under the store."""
        email = staff_in.email.strip().lower()
        existing = cls.get_by_email(db, email)
        if existing:
            raise ValueError(f"An account with email '{email}' already exists.")

        username_clean = (staff_in.username or email.split("@")[0]).strip().lower()
        user = User(
            full_name=staff_in.full_name.strip(),
            username=username_clean,
            phone=staff_in.phone.strip() if staff_in.phone else None,
            email=email,
            password_hash=get_password_hash(staff_in.password),
            role="STAFF",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def list_staff(
        db: Session,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[User]:
        """List staff accounts with optional active filter and pagination."""
        query = select(User).where(User.role == "STAFF").order_by(User.created_at.desc())
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        query = query.offset(skip).limit(limit)
        return list(db.scalars(query).all())

    @classmethod
    def update_staff_status(
        cls,
        db: Session,
        user_id: UUID,
        is_active: bool,
        acting_user: User,
    ) -> User:
        """Activate or deactivate a staff member."""
        if acting_user.id == user_id and not is_active:
            raise ValueError("You cannot deactivate your own account.")

        user = cls.get_by_id(db, user_id)
        if not user:
            raise LookupError(f"User with ID '{user_id}' not found.")

        if user.role == "OWNER" and not is_active:
            raise ValueError("Store OWNER accounts cannot be deactivated.")

        user.is_active = is_active
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(
        db: Session,
        user: User,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change a user's own password after verifying their current password."""
        if not verify_password(current_password, user.password_hash):
            return False

        user.password_hash = get_password_hash(new_password)
        db.commit()
        return True

    @classmethod
    def reset_password(
        cls,
        db: Session,
        user_id: UUID,
        new_password: str,
    ) -> User:
        """Allow owner to reset a staff member's password."""
        user = cls.get_by_id(db, user_id)
        if not user:
            raise LookupError(f"User with ID '{user_id}' not found.")

        user.password_hash = get_password_hash(new_password)
        db.commit()
        db.refresh(user)
        return user
