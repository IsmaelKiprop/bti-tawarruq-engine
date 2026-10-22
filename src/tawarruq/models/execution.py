"""SACCO and bank Sedania Tawarruq executions, plus 7-year certificate vault."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base


class TawarruqExecution(Base):
    """One Sedania facility: SACCO execute, or bank CMP financing through AS SIDQ."""

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
    path: Mapped[str] = mapped_column(String(32), nullable=False, default="sacco", index=True)
    flow_variant: Mapped[str] = mapped_column(String(32), nullable=False, default="approved_wakeel")
    delivery_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="constructive")
    agency_role: Mapped[str] = mapped_column(String(16), nullable=False, default="wakeel")
    agency_party: Mapped[str] = mapped_column(String(64), nullable=False, default="SEDANIA_AS_SALAM_CAPITAL")
    appoint_sasc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    wad_token_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wad_signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wakalah_token_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    wakalah_signature: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sedania_batch_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    purchase_order_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commodity_invoice_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivery_order_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trading_ecert_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    supplier_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    purchaser_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    muqassah_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    muqassah_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    casa_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    casa_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    casa_credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cash_disbursement: Mapped[str] = mapped_column(String(32), nullable=False, default="sacco_cbs")
    physical_delivery_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    physical_delivery_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    physical_delivery_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repayment_settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
