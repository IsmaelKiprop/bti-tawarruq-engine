"""Super Admin platform settings: Sedania % Charge and per-FI BTI % Charge."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from tawarruq.models.institution import Institution
from tawarruq.models.platform_settings import PLATFORM_SETTINGS_ID, PlatformSettings

CHARGE_PLACES = Decimal("0.000001")
RATE_PLACES = Decimal("0.00000001")
DEFAULT_SEDANIA_CHARGE_PCT = Decimal("0.0035")
DEFAULT_BTI_CHARGE_PCT = Decimal("0.004")
LEGACY_SEDANIA_DEFAULT = Decimal("5.00")


def parse_charge_pct(value: Decimal | float | str | None, *, field: str) -> Decimal:
    if value is None or value == "":
        raise ValueError(f"{field} is required")
    pct = Decimal(str(value)).quantize(CHARGE_PLACES, rounding=ROUND_HALF_UP)
    if pct < 0 or pct > 100:
        raise ValueError(f"{field} must be between 0 and 100")
    return pct


def pct_to_rate(pct: Decimal | float | str) -> Decimal:
    return (Decimal(str(pct)) / Decimal("100")).quantize(RATE_PLACES, rounding=ROUND_HALF_UP)


def get_or_create_platform_settings(db: Session) -> PlatformSettings:
    row = db.get(PlatformSettings, PLATFORM_SETTINGS_ID)
    if row:
        stored = Decimal(str(row.sedania_charge_pct))
        if stored == LEGACY_SEDANIA_DEFAULT:
            row.sedania_charge_pct = DEFAULT_SEDANIA_CHARGE_PCT
            db.flush()
        return row
    row = PlatformSettings(
        id=PLATFORM_SETTINGS_ID,
        sedania_charge_pct=DEFAULT_SEDANIA_CHARGE_PCT,
    )
    db.add(row)
    db.flush()
    return row


def sedania_profit_rate(db: Session) -> Decimal:
    """Murabahah rate as a fraction from Super Admin Sedania % Charge."""
    return pct_to_rate(get_or_create_platform_settings(db).sedania_charge_pct)


def bti_charge_rate(institution: Institution | None) -> Decimal:
    pct = getattr(institution, "bti_charge_pct", None)
    if pct is None:
        pct = DEFAULT_BTI_CHARGE_PCT
    return pct_to_rate(pct)


def update_sedania_charge_pct(db: Session, pct: Decimal | float | str, *, actor_id: str | None) -> PlatformSettings:
    row = get_or_create_platform_settings(db)
    row.sedania_charge_pct = parse_charge_pct(pct, field="Sedania % Charge")
    row.updated_by_id = actor_id
    db.flush()
    return row


def update_institution_bti_charge(
    db: Session, institution: Institution, pct: Decimal | float | str
) -> Institution:
    institution.bti_charge_pct = parse_charge_pct(pct, field="BTI % Charge")
    db.flush()
    return institution


def list_institution_charges(db: Session) -> list[Institution]:
    return db.query(Institution).order_by(Institution.name.asc()).all()
