import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base
from tawarruq.enums import TransactionMode


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    bsas_mode: Mapped[str] = mapped_column(String(32), default=TransactionMode.MANUAL_BRIDGE)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approval_steps: Mapped[str] = mapped_column(
        String(256), default="murabaha,liquidation,disbursement", nullable=False
    )
    approval_limit_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    billing_fee_bps: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    applications = relationship("FinancingApplication", back_populates="institution")
    transactions = relationship("CommodityTransaction", back_populates="institution")
    webhooks = relationship("WebhookSubscription", back_populates="institution")
    api_keys = relationship("ApiKey", back_populates="institution")
    customers = relationship("Customer", back_populates="institution")
    liquidity_pool = relationship("LiquidityPool", back_populates="institution", uselist=False)
    integration = relationship("InstitutionIntegration", back_populates="institution", uselist=False)
