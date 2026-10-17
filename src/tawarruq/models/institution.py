import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base
from tawarruq.enums import TransactionMode


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    bsas_mode: Mapped[str] = mapped_column(String(32), default=TransactionMode.MANUAL_BRIDGE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    applications = relationship("FinancingApplication", back_populates="institution")
    transactions = relationship("CommodityTransaction", back_populates="institution")
    webhooks = relationship("WebhookSubscription", back_populates="institution")
    api_keys = relationship("ApiKey", back_populates="institution")
    customers = relationship("Customer", back_populates="institution")
    liquidity_pool = relationship("LiquidityPool", back_populates="institution", uselist=False)
    integration = relationship("InstitutionIntegration", back_populates="institution", uselist=False)
