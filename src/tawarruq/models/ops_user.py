"""Ops portal user accounts (email/password) with RBAC roles."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base
from tawarruq.enums import ApiKeyRole


class OpsUser(Base):
    __tablename__ = "ops_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=ApiKeyRole.INSTITUTION_OPS.value, index=True)
    institution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("institutions.id"), nullable=True, index=True
    )
    agent_dealer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_dealers.id"), nullable=True, index=True
    )
    approval_limit_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ops_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution = relationship("Institution")
