"""Super Admin platform settings: provider, charges, and per-FI BTI % Charge."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from tawarruq.models.institution import Institution
from tawarruq.models.platform_settings import PLATFORM_SETTINGS_ID, PlatformSettings
from tawarruq.models.provider_rate import PROVIDERS, TawarruqProvider, TawarruqProviderRate

CHARGE_PLACES = Decimal("0.000001")
RATE_PLACES = Decimal("0.00000001")
DEFAULT_SEDANIA_CHARGE_PCT = Decimal("0.0035")
DEFAULT_BTI_CHARGE_PCT = Decimal("0.004")
DEFAULT_PROVIDER = "sedania"
LEGACY_SEDANIA_DEFAULT = Decimal("5.00")
DEFAULT_PROVIDER_BOOK = (
    {
        "code": "sedania",
        "company_name": "SEDANIA As Salam Capital Sdn. Bhd.",
        "country": "Malaysia",
        "website": "https://www.sedaniagroup.com",
        "rate_pct": DEFAULT_SEDANIA_CHARGE_PCT,
    },
    {
        "code": "bursa",
        "company_name": "Bursa Malaysia Islamic Services Sdn. Bhd.",
        "country": "Malaysia",
        "website": "https://www.bursamalaysia.com",
        "rate_pct": DEFAULT_SEDANIA_CHARGE_PCT,
    },
)


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


def resolve_active_provider(db: Session, institution_id: str | None = None) -> str:
    if institution_id:
        institution = db.get(Institution, institution_id)
        if institution and getattr(institution, "tawarruq_provider", None):
            try:
                return parse_provider(institution.tawarruq_provider)
            except ValueError:
                pass
    return active_provider(db)


def ensure_default_providers(db: Session) -> list[TawarruqProvider]:
    rows: list[TawarruqProvider] = []
    for seed in DEFAULT_PROVIDER_BOOK:
        row = db.query(TawarruqProvider).filter(TawarruqProvider.code == seed["code"]).first()
        if not row:
            rate = latest_active_rate(db, seed["code"])
            row = TawarruqProvider(
                code=seed["code"],
                company_name=seed["company_name"],
                country=seed["country"],
                website=seed["website"],
                rate_pct=rate.rate_pct if rate else parse_charge_pct(seed["rate_pct"], field="Rate"),
                active=True,
            )
            db.add(row)
            db.flush()
        rows.append(row)
    return rows


def list_providers(db: Session) -> list[TawarruqProvider]:
    ensure_default_providers(db)
    return db.query(TawarruqProvider).order_by(TawarruqProvider.code.asc()).all()


def upsert_provider(
    db: Session,
    *,
    code: str,
    company_name: str,
    country: str,
    website: str,
    rate_pct: Decimal | float | str,
    actor_id: str | None,
) -> TawarruqProvider:
    chosen = parse_provider(code)
    name = (company_name or "").strip()
    if not name:
        raise ValueError("Provider company name is required")
    row = db.query(TawarruqProvider).filter(TawarruqProvider.code == chosen).first()
    if not row:
        row = TawarruqProvider(code=chosen, company_name=name, country="", website="", rate_pct=DEFAULT_SEDANIA_CHARGE_PCT)
        db.add(row)
    row.company_name = name
    row.country = (country or "").strip()
    row.website = (website or "").strip()
    row.rate_pct = parse_charge_pct(rate_pct, field="Rate")
    row.active = True
    db.flush()
    record_provider_rate(db, provider=chosen, rate_pct=row.rate_pct, effective_from=None, actor_id=actor_id)
    return row


def update_institution_provider(db: Session, institution: Institution, provider: str) -> Institution:
    institution.tawarruq_provider = parse_provider(provider)
    db.flush()
    return institution


def resend_is_configured() -> bool:
    from tawarruq.config import get_settings

    return bool((get_settings().resend_api_key or "").strip())


def mail_provider(db: Session | None = None) -> str:
    if resend_is_configured():
        return "resend"
    host, _port, _user, _password, _from_addr = effective_smtp(db)
    if host:
        return "smtp"
    return "none"


def smtp_is_configured(db: Session | None = None) -> bool:
    return mail_provider(db) != "none"


def effective_smtp(db: Session | None = None) -> tuple[str, int, str, str, str]:
    from tawarruq.config import get_settings

    settings = get_settings()
    host = (settings.smtp_host or "").strip()
    port = settings.smtp_port or 587
    user = settings.smtp_user or ""
    password = settings.smtp_password or ""
    from_addr = settings.smtp_from or "amanah@bti-fintech.local"
    row = None
    if db is not None:
        row = get_or_create_platform_settings(db)
    else:
        try:
            from tawarruq.database import SessionLocal

            session = SessionLocal()
            try:
                row = get_or_create_platform_settings(session)
            finally:
                session.close()
        except Exception:
            row = None
    if row and (row.smtp_host or "").strip():
        host = row.smtp_host.strip()
        port = int(row.smtp_port or 587)
        user = row.smtp_user or ""
        password = row.smtp_password or ""
        from_addr = (row.smtp_from or "").strip() or from_addr
    return host, port, user, password, from_addr


def update_smtp_settings(
    db: Session,
    *,
    smtp_host: str | None,
    smtp_port: int | None,
    smtp_user: str | None,
    smtp_password: str | None,
    smtp_from: str | None,
    actor_id: str | None,
) -> PlatformSettings:
    row = get_or_create_platform_settings(db)
    if smtp_host is not None:
        row.smtp_host = smtp_host.strip()
    if smtp_port is not None:
        if smtp_port < 1 or smtp_port > 65535:
            raise ValueError("SMTP port must be between 1 and 65535")
        row.smtp_port = smtp_port
    if smtp_user is not None:
        row.smtp_user = smtp_user.strip()
    if smtp_password:
        row.smtp_password = smtp_password
    if smtp_from is not None:
        row.smtp_from = smtp_from.strip()
    row.updated_by_id = actor_id
    db.flush()
    return row


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
