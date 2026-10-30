"""Super Admin platform settings: provider, charges, and per-FI BTI % Charge."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from tawarruq.models.institution import Institution
from tawarruq.models.platform_settings import PLATFORM_SETTINGS_ID, PlatformSettings
from tawarruq.models.provider_rate import PROVIDERS, TawarruqProviderRate

CHARGE_PLACES = Decimal("0.000001")
RATE_PLACES = Decimal("0.00000001")
DEFAULT_SEDANIA_CHARGE_PCT = Decimal("0.0035")
DEFAULT_BTI_CHARGE_PCT = Decimal("0.004")
DEFAULT_PROVIDER = "sedania"
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


def parse_provider(value: str | None) -> str:
    provider = (value or DEFAULT_PROVIDER).strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("Tawarruq provider must be sedania or bursa")
    return provider


def parse_effective_from(value: datetime | str | None) -> datetime:
    if value is None or value == "":
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Timestamp start must be a date or date-time") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


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


def ensure_default_provider_rate(db: Session) -> TawarruqProviderRate:
    active = (
        db.query(TawarruqProviderRate)
        .filter(TawarruqProviderRate.active.is_(True))
        .order_by(TawarruqProviderRate.effective_from.desc(), TawarruqProviderRate.created_at.desc())
        .first()
    )
    if active:
        return active
    settings = get_or_create_platform_settings(db)
    row = TawarruqProviderRate(
        provider=DEFAULT_PROVIDER,
        rate_pct=parse_charge_pct(settings.sedania_charge_pct, field="Sedania % Charge"),
        effective_from=datetime.now(UTC),
        active=True,
    )
    db.add(row)
    db.flush()
    return row


def latest_active_rate(db: Session, provider: str | None = None) -> TawarruqProviderRate | None:
    query = db.query(TawarruqProviderRate).filter(TawarruqProviderRate.active.is_(True))
    if provider:
        query = query.filter(TawarruqProviderRate.provider == provider)
    return query.order_by(TawarruqProviderRate.effective_from.desc(), TawarruqProviderRate.created_at.desc()).first()


def active_provider(db: Session) -> str:
    row = latest_active_rate(db) or ensure_default_provider_rate(db)
    return row.provider


def sedania_profit_rate(db: Session) -> Decimal:
    """Murabahah rate as a fraction from the latest active Sedania row."""
    row = latest_active_rate(db, "sedania")
    if row:
        return pct_to_rate(row.rate_pct)
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


def record_provider_rate(
    db: Session,
    *,
    provider: str,
    rate_pct: Decimal | float | str,
    effective_from: datetime | str | None,
    actor_id: str | None,
) -> TawarruqProviderRate:
    chosen = parse_provider(provider)
    pct = parse_charge_pct(rate_pct, field="Rate")
    started = parse_effective_from(effective_from)
    for previous in db.query(TawarruqProviderRate).filter(TawarruqProviderRate.provider == chosen, TawarruqProviderRate.active.is_(True)):
        previous.active = False
    if chosen == DEFAULT_PROVIDER:
        update_sedania_charge_pct(db, pct, actor_id=actor_id)
    row = TawarruqProviderRate(
        provider=chosen,
        rate_pct=pct,
        effective_from=started,
        active=True,
        created_by_id=actor_id,
    )
    db.add(row)
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
