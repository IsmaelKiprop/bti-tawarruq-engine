"""In-app notification inbox for Buruuj Lend mobile customers."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from tawarruq.database import Base


class MobileNotification(Base):
    __tablename__ = "mobile_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mobile_accounts.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    application_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sms_queued: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    push_queued: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
