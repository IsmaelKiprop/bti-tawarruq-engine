import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base


class InstitutionIntegration(Base):
    """Per-institution Kenya integration credentials (Daraja, Safaricom/Airtel MNO)."""

    __tablename__ = "institution_integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    institution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("institutions.id"), unique=True, nullable=False, index=True
    )

    kenya_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)  # live | mock | null=inherit global

    # M-Pesa Daraja
    mpesa_env: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mpesa_consumer_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    mpesa_consumer_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    mpesa_shortcode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mpesa_initiator_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mpesa_security_credential: Mapped[str | None] = mapped_column(Text, nullable=True)
    mpesa_stk_passkey: Mapped[str | None] = mapped_column(Text, nullable=True)
    mpesa_b2c_command_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Safaricom MNO dealer API
    mno_safaricom_api_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mno_safaricom_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    mno_safaricom_dealer_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Airtel MNO
    mno_airtel_api_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mno_airtel_token_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mno_airtel_client_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mno_airtel_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Public base URL for this institution's callbacks (e.g. https://bank-a.api.bti.fintech)
    callback_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution = relationship("Institution", back_populates="integration")
