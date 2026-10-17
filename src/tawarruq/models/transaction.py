import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base
from tawarruq.enums import LegStatus, TransactionMode, TransactionStatus, TransactionPhase


class CommodityTransaction(Base):
    __tablename__ = "commodity_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("financing_applications.id"), nullable=False, index=True
    )
    institution_id: Mapped[str] = mapped_column(String(36), ForeignKey("institutions.id"), nullable=False)
    commodity_code: Mapped[str] = mapped_column(String(32), nullable=False, default="AIRTIME_SAFARICOM")
    mode: Mapped[str] = mapped_column(String(32), default=TransactionMode.MNO)
    status: Mapped[str] = mapped_column(String(32), default=TransactionStatus.CREATED, index=True)
    phase: Mapped[str] = mapped_column(String(32), default=TransactionPhase.PHASE_1_PURCHASE)
    mno_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    broker_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("third_party_brokers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    application = relationship("FinancingApplication", back_populates="transactions")
    institution = relationship("Institution", back_populates="transactions")
    legs = relationship("TransactionLeg", back_populates="transaction", order_by="TransactionLeg.leg_number")
    liquidation_order = relationship("LiquidationOrder", back_populates="transaction", uselist=False)


class TransactionLeg(Base):
    __tablename__ = "transaction_legs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("commodity_transactions.id"), nullable=False, index=True
    )
    leg_number: Mapped[str] = mapped_column(String(1), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=LegStatus.PENDING, index=True)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    bsas_fee: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    transaction = relationship("CommodityTransaction", back_populates="legs")
    certificate = relationship("Certificate", back_populates="leg", uselist=False)
    asset_batch = relationship("AssetBatch", back_populates="leg", uselist=False)
