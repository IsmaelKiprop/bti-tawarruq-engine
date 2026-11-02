import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from tawarruq.database import Base

PROVIDERS = ("sedania", "bursa")


class TawarruqProvider(Base):
    """Super Admin book of Tawarruq counterparties. One row per provider code."""

    __tablename__ = "tawarruq_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(256), nullable=False)
    country: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    website: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TawarruqProviderRate(Base):
    """Super Admin history of Tawarruq provider and rate. One active row per provider."""

    __tablename__ = "tawarruq_provider_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ops_users.id"), nullable=True)
