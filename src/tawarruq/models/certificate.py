import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tawarruq.database import Base


class Certificate(Base):
    """BSAS / Bursa Suq Al-Sila' e-certificate (Islamic Services Receipt)."""

    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    leg_id: Mapped[str] = mapped_column(String(36), ForeignKey("transaction_legs.id"), unique=True, nullable=False)
    certificate_number: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    issuer: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Bursa Malaysia Islamic Services Sdn.Bhd.",
    )
    # Bursa receipt fields
    seller: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bid_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    selling_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selling_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    volume: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    price: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_myr_equivalent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_amount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pdf_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    leg = relationship("TransactionLeg", back_populates="certificate")
