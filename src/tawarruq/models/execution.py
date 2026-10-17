"""SACCO-initiated Tawarruq executions and 7-year certificate vault."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base


class TawarruqExecution(Base):
    """One inbound SACCO facility request through Sedania, until ready for SACCO payout."""

    __tablename__ = "tawarruq_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=False, index=True)
    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("financing_applications.id"), nullable=True, index=True
    )
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    client_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    profit_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    deferred_price: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    tenor_months: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="KES")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="received", index=True)
    wad_token_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wad_signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wakalah_token_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wakalah_signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sedania_batch_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    callback_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    callback_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    institution = relationship("Institution")
    application = relationship("FinancingApplication")
    customer = relationship("Customer")
    certificates = relationship("CertificateVault", back_populates="execution")


class CertificateVault(Base):
    """Cached Sedania / Buruuj legal certificates retained for 7 years."""

    __tablename__ = "certificate_vault"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tawarruq_executions.id"), nullable=False, index=True
    )
    institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=False, index=True)
    application_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("financing_applications.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    certificate_number: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    access_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    serial_numbers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    execution = relationship("TawarruqExecution", back_populates="certificates")
