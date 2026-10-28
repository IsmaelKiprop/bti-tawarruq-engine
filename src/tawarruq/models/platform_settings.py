from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from tawarruq.database import Base

PLATFORM_SETTINGS_ID = "default"


class PlatformSettings(Base):
    """Singleton Super Admin platform knobs."""

    __tablename__ = "platform_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=PLATFORM_SETTINGS_ID)
    sedania_charge_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0.0035"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ops_users.id"), nullable=True)
