"""Store settings and receipt configuration model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Numeric, Integer, Text, CheckConstraint, Index, text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class StoreSettings(Base):
    """Store profile, tax preferences, and thermal receipt printing configurations."""

    __tablename__ = "store_settings"
    __table_args__ = (
        CheckConstraint(
            "default_tax_rate >= 0 AND default_tax_rate <= 100",
            name="ck_store_settings_default_tax_rate",
        ),
        CheckConstraint(
            "receipt_width_mm IN (58, 80)",
            name="ck_store_settings_receipt_width_mm",
        ),
        # Ensures only one active configuration can exist in the store
        Index(
            "uq_store_settings_single_active",
            "is_active_config",
            unique=True,
            postgresql_where=text("is_active_config IS TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    store_name: Mapped[str] = mapped_column(String(255), nullable=False, default="VIYON")
    tagline: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default="MEN'S COLLECTIONS",
    )
    logo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="F6WR+R8W, South Rangasamuthram, North Rangasamuthram, Sathyamangalam, Tamil Nadu 638402",
    )
    phone: Mapped[str] = mapped_column(String(50), nullable=False, default="082702 42681")
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    receipt_footer: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default="Thank you for shopping at VIYON! Visit again.",
    )
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    tax_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    receipt_width_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=58)
    is_active_config: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<StoreSettings store_name={self.store_name} phone={self.phone}>"
