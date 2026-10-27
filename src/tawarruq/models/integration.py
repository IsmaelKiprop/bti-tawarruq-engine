import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    events: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    institution = relationship("Institution", back_populates="webhooks")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hmac_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reveal_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="institution_ops", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    institution = relationship("Institution", back_populates="api_keys")
