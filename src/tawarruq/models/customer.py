import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base
from tawarruq.enums import AmlStatus, KycStatus, WalletProvider


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    national_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    id_document_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    selfie_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    kyc_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kyc_status: Mapped[str] = mapped_column(String(32), default=KycStatus.PENDING)
    aml_status: Mapped[str] = mapped_column(String(32), default=AmlStatus.PENDING)
    credit_score: Mapped[int] = mapped_column(Integer, default=0)
    wallet_provider: Mapped[str] = mapped_column(String(32), default=WalletProvider.MPESA)
    wallet_number: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    institution = relationship("Institution", back_populates="customers")
    applications = relationship("FinancingApplication", back_populates="customer")


class LiquidityPool(Base):
    __tablename__ = "liquidity_pools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="KES")
    available_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    reserved_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution = relationship("Institution", back_populates="liquidity_pool")
