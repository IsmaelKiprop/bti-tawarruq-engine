import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base
from tawarruq.enums import ApplicationStatus


class FinancingApplication(Base):
    __tablename__ = "financing_applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True, index=True)
    customer_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    customer_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="KES")
    amount_requested: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    term_months: Mapped[int] = mapped_column(nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=ApplicationStatus.DRAFT, index=True)
    eligibility_passed: Mapped[bool | None] = mapped_column(nullable=True)
    current_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    wad_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    wad_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution = relationship("Institution", back_populates="applications")
    customer = relationship("Customer", back_populates="applications")
    offer = relationship("FinancingOffer", back_populates="application", uselist=False)
    transactions = relationship("CommodityTransaction", back_populates="application")
    disbursements = relationship("Disbursement", back_populates="application")
    customer_sale = relationship("CustomerSale", back_populates="application", uselist=False)
    customer_agency = relationship("CustomerAgency", back_populates="application", uselist=False)
    murabaha_contract = relationship("MurabahaContract", back_populates="application", uselist=False)


class FinancingOffer(Base):
    __tablename__ = "financing_offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("financing_applications.id"), unique=True, nullable=False
    )
    cost_price: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    profit_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    total_payable: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    installment_count: Mapped[int] = mapped_column(default=1)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application = relationship("FinancingApplication", back_populates="offer")
