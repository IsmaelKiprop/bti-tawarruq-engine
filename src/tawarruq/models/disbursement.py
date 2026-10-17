import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base


class Disbursement(Base):
    __tablename__ = "disbursements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("financing_applications.id"), nullable=False, index=True
    )
    transaction_id: Mapped[str] = mapped_column(String(36), ForeignKey("commodity_transactions.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    certificate_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("certificates.id"), nullable=True)
    disbursed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    application = relationship("FinancingApplication", back_populates="disbursements")
    tawarruq_certificate = relationship("TawarruqFinancingCertificate", back_populates="disbursement", uselist=False)
    wallet_disbursement = relationship("WalletDisbursement", back_populates="disbursement", uselist=False)
