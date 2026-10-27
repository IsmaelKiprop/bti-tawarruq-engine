"""FI KYC onboarding: draft, submit, Super Admin decide, lifecycle."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from tawarruq.enums import ApiKeyRole, AuditActor
from tawarruq.models.institution import Institution
from tawarruq.models.institution_profile import InstitutionProfile
from tawarruq.services.audit_service import log_audit

INSTITUTION_TYPES = {
    "SACCO",
    "BANK",
    "MICROFINANCE_BANK",
    "FINTECH",
    "PAYMENT_SERVICE_PROVIDER",
    "DIGITAL_LENDER",
    "OTHER",
}
REGULATORS = {"CBK", "SASRA", "CMA", "IRA", "RBA", "ODPC", "OTHER", "NOT_APPLICABLE"}
LICENCE_STATUSES = {
    "ACTIVE",
    "PENDING",
    "EXPIRED",
    "SUSPENDED",
    "REVOKED",
    "NOT_APPLICABLE",
    "UNDER_VERIFICATION",
}
SCREEN_STATUSES = {
    "NOT_STARTED",
    "CLEAR",
    "POTENTIAL_MATCH",
    "CONFIRMED_MATCH",
    "REVIEW_REQUIRED",
    "NOT_APPLICABLE",
}
ID_TYPES = {"NATIONAL_ID", "PASSPORT", "ALIEN_ID", "OTHER"}
VERIFY_STATUSES = {"NOT_STARTED", "PENDING", "VERIFIED", "FAILED", "REVIEW_REQUIRED", "NOT_APPLICABLE"}
SETTLEMENT_VERIFY = {"NOT_STARTED", "PENDING", "VERIFIED", "FAILED", "REVIEW_REQUIRED"}
AGREEMENT_STATUSES = {"NOT_STARTED", "DRAFT", "UNDER_REVIEW", "SIGNED", "REJECTED", "NOT_APPLICABLE"}
LIFECYCLE = {"draft", "pending_approval", "active", "dormant", "deactivated"}
DECIDE = {"approve", "return", "reject"}

PROFILE_FIELDS = {
    "trading_name",
    "institution_type",
    "other_institution_type",
    "registration_number",
    "incorporation_date",
    "incorporation_country",
    "kra_pin",
    "registered_address_line1",
    "registered_address_line2",
    "registered_county",
    "registered_postal_code",
    "physical_address",
    "website_url",
    "support_email",
    "main_telephone",
    "business_description",
    "primary_regulator",
    "regulator_other_name",
    "licence_number",
    "licence_issue_date",
    "licence_expiry_date",
    "licence_status",
    "regulator_register_url",
    "ownership_structure_summary",
    "parent_company_name",
    "related_entities",
    "owners_and_shareholders",
    "ownership_percentage",
    "ubo_details",
    "directors_board_members",
    "ceo_managing_director_name",
    "senior_management_details",
    "pep_screening_status",
    "sanctions_screening_status",
    "adverse_media_screening_status",
    "primary_contact_full_name",
    "primary_contact_title",
    "primary_contact_work_email",
    "primary_contact_phone",
    "compliance_officer_name",
    "compliance_officer_email",
    "authorized_signatories",
    "representative_id_type",
    "representative_id_number",
    "representative_identity_verification_status",
    "authority_to_act_document_id",
    "settlement_bank_name",
    "settlement_account_name",
    "settlement_branch",
    "settlement_account_number",
    "settlement_currency",
    "settlement_account_verification_status",
    "settlement_account_evidence_document_id",
    "expected_monthly_transaction_count",
    "expected_monthly_transaction_value",
    "typical_transaction_amount",
    "maximum_transaction_amount",
    "target_go_live_date",
    "commercial_agreement_status",
    "pricing_schedule_reference",
    "dispute_contact_email",
}

DATE_FIELDS = {
    "incorporation_date",
    "licence_issue_date",
    "licence_expiry_date",
    "target_go_live_date",
}
DECIMAL_FIELDS = {
    "ownership_percentage",
    "expected_monthly_transaction_value",
    "typical_transaction_amount",
    "maximum_transaction_amount",
}
INT_FIELDS = {"expected_monthly_transaction_count"}
LIST_FIELDS = {
    "related_entities",
    "owners_and_shareholders",
    "ubo_details",
    "directors_board_members",
    "senior_management_details",
    "authorized_signatories",
}

_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
_PHONE = re.compile(r"^\+[1-9]\d{7,14}$")
_NAME = re.compile(r"^[\w][\w\s.,'’&()/\\-]{1,198}$", re.UNICODE)
_CONTACT = re.compile(r"^[\w][\w\s.'-]{1,149}$", re.UNICODE)
_KRA = re.compile(r"^[A-Z]\d{9}[A-Z]$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_URL = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")
_REG_NO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./-]{1,49}$")
_LICENCE = re.compile(r"^[A-Za-z0-9./ -]{2,80}$")
_ACCOUNT = re.compile(r"^[A-Za-z0-9-]{4,34}$")
_ID_NO = re.compile(r"^[A-Za-z0-9/-]{3,40}$")
_COUNT = re.compile(r"^(0|[1-9]\d{0,8})$")
_MONEY = re.compile(r"^\d{1,15}(\.\d{1,2})?$")
_PCT = re.compile(r"^(100(\.0+)?|[0-9]{1,2}(\.[0-9]{1,4})?)$")


def suggest_code(name: str) -> str:
    letters = re.sub(r"[^A-Za-z0-9]", "", name).upper()
    return (letters[:8] or "FI")[:32]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid number: {value}") from exc


def _as_int(value) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _as_list(value) -> list | None:
    if value in (None, ""):
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        return parts or None
    raise ValueError("Expected a list")


def apply_profile_fields(profile: InstitutionProfile, payload: dict) -> None:
    for key, raw in payload.items():
        if key not in PROFILE_FIELDS:
            continue
        if key in DATE_FIELDS:
            setattr(profile, key, _as_date(raw))
        elif key in DECIMAL_FIELDS:
            setattr(profile, key, _as_decimal(raw))
        elif key in INT_FIELDS:
            setattr(profile, key, _as_int(raw))
        elif key in LIST_FIELDS:
            setattr(profile, key, _as_list(raw))
        elif isinstance(raw, str):
            cleaned = raw.strip()
            setattr(profile, key, cleaned or None)
        else:
            setattr(profile, key, raw)


def _req(value, label: str) -> str:
    text = (value or "").strip() if isinstance(value, str) else value
    if text in (None, ""):
        raise ValueError(f"{label} is required")
    return str(text)


def _match(pattern: re.Pattern, value: str | None, label: str) -> None:
    if value in (None, ""):
        return
    if not pattern.match(str(value)):
        raise ValueError(f"{label} is not valid")


def validate_for_submit(institution: Institution, profile: InstitutionProfile) -> None:
    name = _req(institution.name, "Legal registered name")
    if not _NAME.match(name):
        raise ValueError("Legal registered name is not valid")
    itype = _req(profile.institution_type, "Institution type")
    if itype not in INSTITUTION_TYPES:
        raise ValueError("Institution type is not valid")
    if itype == "OTHER":
        _req(profile.other_institution_type, "Other institution type")
    _match(_EMAIL, _req(profile.support_email, "Support email"), "Support email")
    _match(_PHONE, _req(profile.main_telephone, "Main telephone"), "Main telephone")
    _match(_REG_NO, profile.registration_number, "Registration number")
    _match(_COUNTRY, (profile.incorporation_country or "").upper() or None, "Incorporation country")
    if profile.incorporation_country:
        profile.incorporation_country = profile.incorporation_country.upper()
    _match(_KRA, profile.kra_pin, "KRA PIN")
    if profile.website_url:
        _match(_URL, profile.website_url, "Website")

    regulator = _req(profile.primary_regulator, "Primary regulator")
    if regulator not in REGULATORS:
        raise ValueError("Primary regulator is not valid")
    if regulator == "OTHER":
        _req(profile.regulator_other_name, "Regulator name")
    _match(_LICENCE, _req(profile.licence_number, "Licence number"), "Licence number")
    if not profile.licence_issue_date:
        raise ValueError("Licence issue date is required")
    status = _req(profile.licence_status, "Licence status")
    if status not in LICENCE_STATUSES:
        raise ValueError("Licence status is not valid")
    if profile.regulator_register_url:
        _match(_URL, profile.regulator_register_url, "Regulator register URL")

    for field, allowed in (
        ("pep_screening_status", SCREEN_STATUSES),
        ("sanctions_screening_status", SCREEN_STATUSES),
        ("adverse_media_screening_status", SCREEN_STATUSES),
    ):
        value = getattr(profile, field) or "NOT_STARTED"
        if value not in allowed:
            raise ValueError(f"{field} is not valid")
        setattr(profile, field, value)
    if profile.ownership_percentage is not None and not _PCT.match(str(profile.ownership_percentage)):
        raise ValueError("Ownership percentage is not valid")

    _match(_CONTACT, _req(profile.primary_contact_full_name, "Primary contact name"), "Primary contact name")
    _req(profile.primary_contact_title, "Primary contact title")
    _match(_EMAIL, _req(profile.primary_contact_work_email, "Primary contact email"), "Primary contact email")
    _match(_PHONE, _req(profile.primary_contact_phone, "Primary contact phone"), "Primary contact phone")
    _match(_EMAIL, profile.compliance_officer_email, "Compliance officer email")
    signatories = profile.authorized_signatories or []
    if not signatories:
        raise ValueError("At least one authorized signatory is required")
    id_type = _req(profile.representative_id_type, "Representative ID type")
    if id_type not in ID_TYPES:
        raise ValueError("Representative ID type is not valid")
    _match(_ID_NO, _req(profile.representative_id_number, "Representative ID number"), "Representative ID number")
    id_status = _req(profile.representative_identity_verification_status, "Identity verification status")
    if id_status not in VERIFY_STATUSES:
        raise ValueError("Identity verification status is not valid")
    _req(profile.authority_to_act_document_id, "Authority to act document reference")

    _req(profile.settlement_bank_name, "Settlement bank")
    _req(profile.settlement_account_name, "Settlement account name")
    _match(_ACCOUNT, _req(profile.settlement_account_number, "Settlement account number"), "Settlement account number")
    currency = _req(profile.settlement_currency, "Settlement currency").upper()
    _match(_CURRENCY, currency, "Settlement currency")
    profile.settlement_currency = currency
    settle_status = _req(profile.settlement_account_verification_status, "Settlement verification status")
    if settle_status not in SETTLEMENT_VERIFY:
        raise ValueError("Settlement verification status is not valid")

    count = profile.expected_monthly_transaction_count
    if count is None or not _COUNT.match(str(count)):
        raise ValueError("Expected monthly transaction count is required")
    for field, label in (
        ("expected_monthly_transaction_value", "Expected monthly transaction value"),
        ("typical_transaction_amount", "Typical transaction amount"),
        ("maximum_transaction_amount", "Maximum transaction amount"),
    ):
        raw = getattr(profile, field)
        if raw is None or not _MONEY.match(str(raw)):
            raise ValueError(f"{label} is required")
    if not profile.target_go_live_date:
        raise ValueError("Target go-live date is required")
    agreement = _req(profile.commercial_agreement_status, "Commercial agreement status")
    if agreement not in AGREEMENT_STATUSES:
        raise ValueError("Commercial agreement status is not valid")
    _match(_EMAIL, profile.dispute_contact_email, "Dispute contact email")


def _sync_active(institution: Institution) -> None:
    institution.active = institution.lifecycle_status == "active"


def get_or_create_profile(db: Session, institution: Institution, actor_id: str | None) -> InstitutionProfile:
    profile = db.get(InstitutionProfile, institution.id)
    if profile:
        return profile
    profile = InstitutionProfile(
        institution_id=institution.id,
        pep_screening_status="NOT_STARTED",
        sanctions_screening_status="NOT_STARTED",
        adverse_media_screening_status="NOT_STARTED",
        application_status="DRAFT",
        approval_decision="PENDING",
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(profile)
    db.flush()
    return profile


def start_onboarding(
    db: Session,
    *,
    legal_name: str,
    code: str | None,
    actor_id: str | None,
    profile_fields: dict | None = None,
) -> tuple[Institution, InstitutionProfile]:
    name = (legal_name or "").strip()
    if not name:
        raise ValueError("Legal registered name is required")
    inst_code = (code or suggest_code(name)).strip().upper()
    if db.query(Institution).filter(Institution.code == inst_code).first():
        raise ValueError(f"Institution code {inst_code} already exists")
    institution = Institution(name=name, code=inst_code, lifecycle_status="draft", active=False)
    db.add(institution)
    db.flush()
    profile = get_or_create_profile(db, institution, actor_id)
    if profile_fields:
        apply_profile_fields(profile, profile_fields)
    profile.updated_by = actor_id
    log_audit(
        db,
        entity_type="institution",
        entity_id=institution.id,
        actor=AuditActor.HUMAN,
        action="institution.onboarding.started",
        details=f"code={institution.code}",
        institution_id=institution.id,
        actor_user_id=actor_id,
        action_group="institutions",
    )
    return institution, profile


def save_onboarding(
    db: Session,
    institution: Institution,
    *,
    legal_name: str | None,
    code: str | None,
    actor_id: str | None,
    profile_fields: dict | None = None,
) -> tuple[Institution, InstitutionProfile]:
    if institution.lifecycle_status in {"deactivated"} and institution.code.upper() != "DEFAULT":
        raise ValueError("This financial institution is deactivated")
    if legal_name is not None:
        cleaned = legal_name.strip()
        if not cleaned:
            raise ValueError("Legal registered name is required")
        institution.name = cleaned
    if code is not None:
        next_code = code.strip().upper()
        if next_code and next_code != institution.code:
            clash = db.query(Institution).filter(Institution.code == next_code).first()
            if clash:
                raise ValueError(f"Institution code {next_code} already exists")
            institution.code = next_code
    profile = get_or_create_profile(db, institution, actor_id)
    if profile_fields:
        apply_profile_fields(profile, profile_fields)
    profile.updated_by = actor_id
    log_audit(
        db,
        entity_type="institution",
        entity_id=institution.id,
        actor=AuditActor.HUMAN,
        action="institution.onboarding.saved",
        details=f"code={institution.code}",
        institution_id=institution.id,
        actor_user_id=actor_id,
        action_group="institutions",
    )
    return institution, profile


def submit_onboarding(
    db: Session,
    institution: Institution,
    *,
    actor_id: str | None,
    role: str | None,
) -> tuple[Institution, InstitutionProfile]:
    profile = get_or_create_profile(db, institution, actor_id)
    validate_for_submit(institution, profile)
    now = _now()
    profile.submission_date = now
    profile.updated_by = actor_id
    if role == ApiKeyRole.PLATFORM_ADMIN.value:
        institution.lifecycle_status = "active"
        profile.application_status = "ACTIVE"
        profile.approval_decision = "APPROVED"
        profile.approver_id = actor_id
        profile.approval_timestamp = now
        profile.activation_date = now.date()
        action = "institution.onboarding.activated"
    else:
        institution.lifecycle_status = "pending_approval"
        profile.application_status = "UNDER_REVIEW"
        profile.approval_decision = "PENDING"
        action = "institution.onboarding.submitted"
    _sync_active(institution)
    log_audit(
        db,
        entity_type="institution",
        entity_id=institution.id,
        actor=AuditActor.HUMAN,
        action=action,
        details=f"code={institution.code}, lifecycle={institution.lifecycle_status}",
        institution_id=institution.id,
        actor_user_id=actor_id,
        action_group="institutions",
    )
    return institution, profile


def decide_onboarding(
    db: Session,
    institution: Institution,
    *,
    decision: str,
    reason: str | None,
    actor_id: str | None,
) -> tuple[Institution, InstitutionProfile]:
    if decision not in DECIDE:
        raise ValueError("Decision must be approve, return, or reject")
    profile = get_or_create_profile(db, institution, actor_id)
    now = _now()
    profile.approver_id = actor_id
    profile.approval_timestamp = now
    profile.approval_reason = (reason or "").strip() or None
    profile.updated_by = actor_id
    if decision == "approve":
        validate_for_submit(institution, profile)
        institution.lifecycle_status = "active"
        profile.application_status = "ACTIVE"
        profile.approval_decision = "APPROVED"
        profile.activation_date = now.date()
    elif decision == "return":
        institution.lifecycle_status = "draft"
        profile.application_status = "PENDING_INFORMATION"
        profile.approval_decision = "RETURNED_FOR_INFORMATION"
    else:
        institution.lifecycle_status = "deactivated"
        profile.application_status = "REJECTED"
        profile.approval_decision = "REJECTED"
    _sync_active(institution)
    log_audit(
        db,
        entity_type="institution",
        entity_id=institution.id,
        actor=AuditActor.HUMAN,
        action=f"institution.onboarding.{decision}",
        details=f"code={institution.code}",
        institution_id=institution.id,
        actor_user_id=actor_id,
        action_group="institutions",
    )
    return institution, profile


def set_lifecycle(
    db: Session,
    institution: Institution,
    *,
    status: str,
    actor_id: str | None,
) -> Institution:
    if status not in {"active", "dormant", "deactivated"}:
        raise ValueError("Lifecycle must be active, dormant, or deactivated")
    if status == "active":
        profile = db.get(InstitutionProfile, institution.id)
        if profile:
            validate_for_submit(institution, profile)
    institution.lifecycle_status = status
    _sync_active(institution)
    log_audit(
        db,
        entity_type="institution",
        entity_id=institution.id,
        actor=AuditActor.HUMAN,
        action="institution.lifecycle.set",
        details=f"code={institution.code}, lifecycle={status}",
        institution_id=institution.id,
        actor_user_id=actor_id,
        action_group="institutions",
    )
    return institution


def assert_institution_invitable(institution: Institution | None) -> None:
    if institution is None:
        return
    if institution.lifecycle_status != "active" or not institution.active:
        raise ValueError("Invite FI Admin only after this financial institution is active")


def summarize_institutions(db: Session) -> dict:
    rows = db.query(Institution).all()
    profiles = {p.institution_id: p for p in db.query(InstitutionProfile).all()}
    by_type: dict[str, int] = {}
    by_regulator: dict[str, int] = {}
    by_month: dict[str, int] = {}
    by_lifecycle = {key: 0 for key in ("active", "dormant", "deactivated", "draft", "pending_approval")}
    for inst in rows:
        status = inst.lifecycle_status or ("active" if inst.active else "deactivated")
        by_lifecycle[status] = by_lifecycle.get(status, 0) + 1
        profile = profiles.get(inst.id)
        itype = (profile.institution_type if profile and profile.institution_type else "UNSET")
        regulator = (profile.primary_regulator if profile and profile.primary_regulator else "UNSET")
        by_type[itype] = by_type.get(itype, 0) + 1
        by_regulator[regulator] = by_regulator.get(regulator, 0) + 1
        created = inst.created_at
        if created:
            key = created.strftime("%Y-%m")
            by_month[key] = by_month.get(key, 0) + 1
    return {
        "total": len(rows),
        "by_type": by_type,
        "by_regulator": by_regulator,
        "by_month": dict(sorted(by_month.items())),
        "by_lifecycle": by_lifecycle,
        "active": by_lifecycle.get("active", 0),
        "dormant": by_lifecycle.get("dormant", 0),
        "deactivated": by_lifecycle.get("deactivated", 0),
    }
