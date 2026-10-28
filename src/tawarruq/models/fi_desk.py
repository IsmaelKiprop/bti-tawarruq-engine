import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base


class FiDeskCase(Base):
    __tablename__ = "fi_desk_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=False, index=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    assigned_approver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ops_users.id"), nullable=True, index=True)
    requested_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ops_users.id"), nullable=True)
    approval_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    otp_purpose: Mapped[str | None] = mapped_column(String(32), nullable=True)
    otp_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    institution = relationship("Institution")
    assigned_approver = relationship("OpsUser", foreign_keys=[assigned_approver_id])
    requested_by = relationship("OpsUser", foreign_keys=[requested_by_id])
