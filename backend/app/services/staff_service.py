"""Staff management business logic, activity auditing, and cashier administration."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID, uuid4
import logging

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.core.token_blacklist import token_blacklist
from app.models.audit_log import AuditLog
from app.models.bill import Bill
from app.models.user import User
from app.schemas.user import (
    AdminPasswordReset,
    StaffActivityBill,
    StaffActivityOut,
    StaffCreate,
    StaffMetricsOut,
    StaffUpdate,
)

logger = logging.getLogger("viyon_billing")


class StaffService:
    """Service providing comprehensive billing staff and cashier administration."""

    @classmethod
    def get_metrics(cls, db: Session) -> StaffMetricsOut:
        """Calculate real-time staff statistics for dashboard summary cards."""
        now_utc = datetime.now(timezone.utc)
        first_of_month = datetime(now_utc.year, now_utc.month, 1, tzinfo=timezone.utc)

        total_staff = (
            db.scalar(
                select(func.count(User.id)).where(User.role == "STAFF")
            )
            or 0
        )
        active_staff = (
            db.scalar(
                select(func.count(User.id)).where(
                    User.role == "STAFF", User.is_active == True
                )
            )
            or 0
        )
        inactive_staff = (
            db.scalar(
                select(func.count(User.id)).where(
                    User.role == "STAFF", User.is_active == False
                )
            )
            or 0
        )
        created_this_month = (
            db.scalar(
                select(func.count(User.id)).where(
                    User.role == "STAFF", User.created_at >= first_of_month
                )
            )
            or 0
        )

        return StaffMetricsOut(
            total_staff=total_staff,
            active_staff=active_staff,
            inactive_staff=inactive_staff,
            created_this_month=created_this_month,
        )

    @classmethod
    def list_staff(
        cls,
        db: Session,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        role: Optional[str] = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[User], int]:
        """List staff with multi-field search, status filtering, and pagination."""
        query = select(User)

        # 1. Role filter (default to STAFF, or OWNER/STAFF if requested)
        if role:
            query = query.where(User.role == role.strip().upper())
        else:
            query = query.where(User.role == "STAFF")

        # 2. Active status filter
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        # 3. Search filter across name, username, phone, email
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(User.full_name).ilike(term),
                    func.lower(User.username).ilike(term),
                    func.lower(User.email).ilike(term),
                    User.phone.ilike(term),
                )
            )

        # 4. Count total matching
        total_count = db.scalar(select(func.count()).select_from(query.subquery())) or 0

        # 5. Sorting
        order_col = getattr(User, sort_by, User.created_at)
        query = query.order_by(order_col.desc() if sort_desc else order_col.asc())

        # 6. Pagination
        query = query.offset(skip).limit(limit)
        staff_records = list(db.scalars(query).all())

        return staff_records, total_count

    @classmethod
    def get_staff_by_id(cls, db: Session, staff_id: UUID) -> User:
        """Fetch staff member by UUID or raise 404."""
        user = db.scalar(select(User).where(User.id == staff_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Staff account with ID '{staff_id}' was not found.",
            )
        return user

    @classmethod
    def create_staff(
        cls,
        db: Session,
        staff_in: StaffCreate,
        current_owner: User,
        ip_address: Optional[str] = None,
    ) -> User:
        """Register a new cashier/staff account with validation and audit logging."""
        now_utc = datetime.now(timezone.utc)

        # 1. Enforce unique username
        username_clean = (staff_in.username or "").strip().lower()
        if username_clean:
            duplicate_username = db.scalar(
                select(User).where(func.lower(User.username) == username_clean)
            )
            if duplicate_username:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Username '{username_clean}' is already taken by another account.",
                )

        # 2. Enforce unique email
        email_clean = (staff_in.email or f"{username_clean}@viyon.store").strip().lower()
        duplicate_email = db.scalar(
            select(User).where(func.lower(User.email) == email_clean)
        )
        if duplicate_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email address '{email_clean}' is already registered.",
            )

        # 3. Enforce unique phone if provided
        phone_clean = staff_in.phone.strip() if staff_in.phone else None
        if phone_clean:
            duplicate_phone = db.scalar(
                select(User).where(User.phone == phone_clean)
            )
            if duplicate_phone:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Phone number '{phone_clean}' is already registered to another account.",
                )

        # 4. Create user record
        new_staff = User(
            id=uuid4(),
            full_name=staff_in.full_name.strip(),
            username=username_clean or email_clean.split("@")[0],
            phone=phone_clean,
            email=email_clean,
            password_hash=get_password_hash(staff_in.password),
            role="STAFF",
            is_active=True,
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(new_staff)
        db.flush()

        # 4. Audit Log
        audit = AuditLog(
            id=uuid4(),
            user_id=current_owner.id,
            action="STAFF_CREATED",
            entity_type="USER",
            entity_id=new_staff.id,
            new_values={
                "staff_id": str(new_staff.id),
                "full_name": new_staff.full_name,
                "username": new_staff.username,
                "email": new_staff.email,
                "phone": new_staff.phone,
                "role": new_staff.role,
                "is_active": new_staff.is_active,
                "created_by": str(current_owner.id),
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)
        db.commit()
        db.refresh(new_staff)

        logger.info(
            f"Staff account created: ID={new_staff.id} Username={new_staff.username} "
            f"ByOwner={current_owner.id}"
        )
        return new_staff

    @classmethod
    def update_staff(
        cls,
        db: Session,
        staff_id: UUID,
        staff_update: StaffUpdate,
        current_owner: User,
        ip_address: Optional[str] = None,
    ) -> User:
        """Update staff member profile (full name, phone, email) with audit logging."""
        staff = cls.get_staff_by_id(db, staff_id)
        now_utc = datetime.now(timezone.utc)

        old_values = {
            "full_name": staff.full_name,
            "phone": staff.phone,
            "email": staff.email,
        }

        # Check unique email if updating email
        if staff_update.email:
            new_email = staff_update.email.strip().lower()
            if new_email != staff.email.lower():
                duplicate = db.scalar(
                    select(User).where(
                        func.lower(User.email) == new_email, User.id != staff.id
                    )
                )
                if duplicate:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Email '{new_email}' is already taken by another user.",
                    )
                staff.email = new_email

        if staff_update.full_name is not None:
            staff.full_name = staff_update.full_name.strip()

        if staff_update.phone is not None:
            staff.phone = staff_update.phone.strip() if staff_update.phone else None

        staff.updated_at = now_utc

        audit = AuditLog(
            id=uuid4(),
            user_id=current_owner.id,
            action="STAFF_PROFILE_UPDATED",
            entity_type="USER",
            entity_id=staff.id,
            old_values=old_values,
            new_values={
                "full_name": staff.full_name,
                "phone": staff.phone,
                "email": staff.email,
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)
        db.commit()
        db.refresh(staff)
        return staff

    @classmethod
    def set_staff_status(
        cls,
        db: Session,
        staff_id: UUID,
        is_active: bool,
        current_owner: User,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> User:
        """Activate or deactivate a staff member with safety checks and audit logging."""
        staff = cls.get_staff_by_id(db, staff_id)
        now_utc = datetime.now(timezone.utc)

        # Prevent owner deactivating their own account
        if staff.id == current_owner.id and not is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own owner account.",
            )

        # Prevent deactivating any account with OWNER role
        if staff.role == "OWNER" and not is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Store OWNER accounts cannot be deactivated.",
            )

        if staff.is_active == is_active:
            return staff  # No-op if status unchanged

        action_name = "STAFF_ACTIVATED" if is_active else "STAFF_DEACTIVATED"
        staff.is_active = is_active
        staff.updated_at = now_utc

        if not is_active:
            token_blacklist.revoke_user_sessions(staff.id)

        audit = AuditLog(
            id=uuid4(),
            user_id=current_owner.id,
            action=action_name,
            entity_type="USER",
            entity_id=staff.id,
            old_values={"is_active": not is_active},
            new_values={
                "is_active": is_active,
                "reason": reason.strip() if reason else None,
                "actioned_by": str(current_owner.id),
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)
        db.commit()
        db.refresh(staff)

        logger.info(
            f"Staff status updated: ID={staff.id} Active={staff.is_active} Action={action_name}"
        )
        return staff

    @classmethod
    def reset_password(
        cls,
        db: Session,
        staff_id: UUID,
        reset_in: AdminPasswordReset,
        current_owner: User,
        ip_address: Optional[str] = None,
    ) -> User:
        """Owner-authorized password reset for cashier accounts with audit logging."""
        staff = cls.get_staff_by_id(db, staff_id)
        now_utc = datetime.now(timezone.utc)

        staff.password_hash = get_password_hash(reset_in.new_password)
        staff.updated_at = now_utc

        # Immediately revoke all active sessions across all devices for this cashier
        token_blacklist.revoke_user_sessions(staff.id)

        audit = AuditLog(
            id=uuid4(),
            user_id=current_owner.id,
            action="STAFF_PASSWORD_RESET",
            entity_type="USER",
            entity_id=staff.id,
            new_values={
                "reset_by": str(current_owner.id),
                "timestamp": now_utc.isoformat(),
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)
        db.commit()
        db.refresh(staff)

        logger.info(f"Staff password reset: StaffID={staff.id} ByOwner={current_owner.id}")
        return staff

    @classmethod
    def get_staff_activity(
        cls,
        db: Session,
        staff_id: UUID,
        limit: int = 50,
    ) -> StaffActivityOut:
        """Retrieve real sales and billing activity attributed to this staff member."""
        staff = cls.get_staff_by_id(db, staff_id)

        # 1. Total bills created
        total_bills_count = (
            db.scalar(
                select(func.count(Bill.id)).where(Bill.staff_user_id == staff_id)
            )
            or 0
        )

        # 2. Completed bills count
        completed_bills_count = (
            db.scalar(
                select(func.count(Bill.id)).where(
                    Bill.staff_user_id == staff_id, Bill.bill_status == "COMPLETED"
                )
            )
            or 0
        )

        # 3. Cancelled bills count
        cancelled_bills_count = (
            db.scalar(
                select(func.count(Bill.id)).where(
                    Bill.staff_user_id == staff_id, Bill.bill_status == "CANCELLED"
                )
            )
            or 0
        )

        # 4. Confirmed sales total (actual amount collected on completed bills)
        sales_sum = db.scalar(
            select(func.sum(Bill.amount_paid)).where(
                Bill.staff_user_id == staff_id, Bill.bill_status == "COMPLETED"
            )
        )
        confirmed_sales_total = (
            Decimal(str(sales_sum)).quantize(Decimal("0.01"))
            if sales_sum is not None
            else Decimal("0.00")
        )

        # 5. Recent bills query
        recent_query = (
            select(Bill)
            .where(Bill.staff_user_id == staff_id)
            .order_by(Bill.created_at.desc())
            .limit(limit)
        )
        bills = list(db.scalars(recent_query).all())

        recent_bills_list = [
            StaffActivityBill(
                id=b.id,
                bill_number=b.bill_number,
                created_at=b.created_at,
                total_amount=b.total_amount,
                amount_paid=b.amount_paid,
                balance_amount=b.balance_amount,
                payment_status=b.payment_status,
                bill_status=b.bill_status,
                is_cancelled=b.bill_status == "CANCELLED",
            )
            for b in bills
        ]

        employee_code = f"EMP-{str(staff.id)[:6].upper()}"

        return StaffActivityOut(
            staff_id=staff.id,
            employee_id=employee_code,
            full_name=staff.full_name,
            username=staff.username,
            email=staff.email,
            phone=staff.phone,
            role=staff.role,
            is_active=staff.is_active,
            date_joined=staff.created_at,
            last_login_at=staff.last_login_at,
            total_bills_count=total_bills_count,
            completed_bills_count=completed_bills_count,
            cancelled_bills_count=cancelled_bills_count,
            confirmed_sales_total=confirmed_sales_total,
            recent_bills=recent_bills_list,
        )

    @classmethod
    def remove_staff(
        cls,
        db: Session,
        staff_id: UUID,
        current_owner: User,
        ip_address: Optional[str] = None,
    ) -> dict:
        """Safely remove a staff account:
        - If staff member has created historical bills, payments, or transactions:
          perform safe deactivation (soft delete), invalidate active sessions, and preserve records.
        - If staff member has no transaction history:
          permanently remove user record.
        - Strictly forbids removing OWNER accounts or self-removal.
        """
        # 1. Prevent removing own account
        if staff_id == current_owner.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot remove your own owner account.",
            )

        # 2. Get target user
        staff = cls.get_staff_by_id(db, staff_id)

        # 3. Prevent removing any account with OWNER role
        if staff.role == "OWNER":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Store OWNER accounts cannot be removed.",
            )

        now_utc = datetime.now(timezone.utc)

        # 4. Check for dependent transaction records
        from app.models.payment import Payment

        bills_count = db.scalar(
            select(func.count(Bill.id)).where(
                or_(
                    Bill.staff_user_id == staff.id,
                    Bill.cancelled_by_user_id == staff.id,
                )
            )
        ) or 0

        payments_count = db.scalar(
            select(func.count(Payment.id)).where(
                or_(
                    Payment.received_by_user_id == staff.id,
                    Payment.confirmed_by_user_id == staff.id,
                )
            )
        ) or 0

        # Check purchase orders, goods receipts, and supplier payments
        po_count = 0
        try:
            from app.models.purchase import PurchaseOrder, GoodsReceipt, SupplierPayment
            po_count = db.scalar(
                select(func.count(PurchaseOrder.id)).where(PurchaseOrder.created_by_user_id == staff.id)
            ) or 0
            gr_count = db.scalar(
                select(func.count(GoodsReceipt.id)).where(GoodsReceipt.received_by_user_id == staff.id)
            ) or 0
            sp_count = db.scalar(
                select(func.count(SupplierPayment.id)).where(
                    or_(
                        SupplierPayment.created_by_user_id == staff.id,
                        SupplierPayment.confirmed_by_user_id == staff.id,
                    )
                )
            ) or 0
            po_count += gr_count + sp_count
        except ImportError:
            pass

        # Check expenses and returns
        extra_count = 0
        try:
            from app.models.expense import Expense
            exp_count = db.scalar(
                select(func.count(Expense.id)).where(
                    or_(
                        Expense.created_by_user_id == staff.id,
                        Expense.voided_by_user_id == staff.id,
                    )
                )
            ) or 0
            extra_count += exp_count
        except ImportError:
            pass

        try:
            from app.models.returns import Return
            ret_count = db.scalar(
                select(func.count(Return.id)).where(Return.processed_by_user_id == staff.id)
            ) or 0
            extra_count += ret_count
        except ImportError:
            pass

        total_tx_count = bills_count + payments_count + po_count + extra_count
        has_transactions = total_tx_count > 0

        # Invalidate active sessions immediately
        token_blacklist.revoke_user_sessions(staff.id)

        if has_transactions:
            # Soft-delete / deactivate
            staff.is_active = False
            # Scramble password hash to prevent future logins
            staff.password_hash = get_password_hash(uuid4().hex + "REVOKED")
            staff.updated_at = now_utc

            audit = AuditLog(
                id=uuid4(),
                user_id=current_owner.id,
                action="STAFF_REMOVED",
                entity_type="USER",
                entity_id=staff.id,
                old_values={"is_active": True},
                new_values={
                    "is_active": False,
                    "soft_deleted": True,
                    "actioned_by": str(current_owner.id),
                    "reason": "Staff removed by store owner (deactivated to preserve sales history)",
                },
                ip_address=ip_address,
                created_at=now_utc,
            )
            db.add(audit)
            db.commit()

            logger.info(
                f"Staff account safely soft-deleted/deactivated: ID={staff.id} "
                f"Username={staff.username} ByOwner={current_owner.id}"
            )
            return {
                "message": (
                    f"Staff account '{staff.full_name}' ({staff.username}) has {bills_count + payments_count} "
                    "historical sales/payment records. The account was safely deactivated and removed "
                    "from active staff to preserve audit and invoice history."
                ),
                "soft_deleted": True,
            }

        # Hard-delete when no transactions exist
        staff_name = staff.full_name
        staff_username = staff.username
        audit = AuditLog(
            id=uuid4(),
            user_id=current_owner.id,
            action="STAFF_PERMANENTLY_DELETED",
            entity_type="USER",
            entity_id=staff.id,
            old_values={"username": staff_username, "full_name": staff_name},
            new_values={
                "deleted": True,
                "actioned_by": str(current_owner.id),
            },
            ip_address=ip_address,
            created_at=now_utc,
        )
        db.add(audit)
        db.delete(staff)
        db.commit()

        logger.info(
            f"Staff account permanently deleted: ID={staff_id} "
            f"Username={staff_username} ByOwner={current_owner.id}"
        )
        return {
            "message": f"Staff account '{staff_name}' ({staff_username}) was permanently removed.",
            "soft_deleted": False,
        }
