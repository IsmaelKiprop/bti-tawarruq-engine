import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base
from tawarruq.enums import AgencyStatus


class CustomerSale(Base):
    """Step 7: Institution sells commodity to customer on deferred payment."""

    __tablename__ = "customer_sales"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("financing_applications.id"), unique=True, nullable=False
    )
    cost_price: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    profit_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    total_payable: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application = relationship("FinancingApplication", back_populates="customer_sale")


class CustomerAgency(Base):
    """Step 8: Customer appoints institution as agent to sell commodity."""

    __tablename__ = "customer_agencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("financing_applications.id"), unique=True, nullable=False
    )
    agent_institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=False)
    broker_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("third_party_brokers.id"), nullable=True)
    is_independent_liquidator: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(32), default=AgencyStatus.ACTIVE)
    appointed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    application = relationship("FinancingApplication", back_populates="customer_agency")


class TawarruqFinancingCertificate(Base):
    """Step 12: Final Tawarruq financing certificate issued to customer."""

    __tablename__ = "tawarruq_financing_certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey("financing_applications.id"), nullable=False)
    disbursement_id: Mapped[str] = mapped_column(String(36), ForeignKey("disbursements.id"), unique=True, nullable=False)
    certificate_number: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    disbursement = relationship("Disbursement", back_populates="tawarruq_certificate")


class HumanHandoff(Base):
    __tablename__ = "human_handoffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
