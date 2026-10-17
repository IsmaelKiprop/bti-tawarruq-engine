from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.integrations.config import InstitutionIntegrationProfile
from tawarruq.models.institution import Institution
from tawarruq.models.institution_integration import InstitutionIntegration
from tawarruq.services.secret_service import decrypt_secret, encrypt_secret


def _callback_urls(institution_id: str, base: str, api_prefix: str) -> dict[str, str]:
    base = base.rstrip("/")
    prefix = api_prefix.rstrip("/")
    root = f"{base}{prefix}/kenya/callbacks/{institution_id}"
    return {
        "mpesa_b2c_result_url": f"{root}/mpesa/b2c/result",
        "mpesa_b2c_timeout_url": f"{root}/mpesa/b2c/timeout",
        "mpesa_stk_callback_url": f"{root}/mpesa/stk",
        "mno_possession_callback_url": f"{root}/mno/possession",
        "mpesa_status_result_url": f"{root}/mpesa/b2c/result",
        "mpesa_status_timeout_url": f"{root}/mpesa/b2c/timeout",
    }


def get_institution_callback_urls(db: Session, institution_id: str) -> dict[str, str]:
    institution = db.get(Institution, institution_id)
    if not institution:
        raise ValueError(f"Institution {institution_id} not found")

    settings = get_settings()
    record = db.query(InstitutionIntegration).filter(InstitutionIntegration.institution_id == institution_id).first()
    base = (record.callback_base_url if record and record.callback_base_url else None) or settings.public_api_base_url
    if not base:
        raise ValueError(
            "callback_base_url not set on institution integration and PUBLIC_API_BASE_URL is not configured"
        )
    return _callback_urls(institution_id, base, settings.api_prefix)


def resolve_integration_profile(db: Session, institution_id: str) -> InstitutionIntegrationProfile:
    settings = get_settings()
    record = db.query(InstitutionIntegration).filter(InstitutionIntegration.institution_id == institution_id).first()

    kenya_mode = settings.kenya_integration_mode
    if record and record.kenya_mode:
        kenya_mode = record.kenya_mode

    try:
        callbacks = get_institution_callback_urls(db, institution_id)
    except ValueError:
        callbacks = {
            "mpesa_b2c_result_url": settings.mpesa_b2c_result_url,
            "mpesa_b2c_timeout_url": settings.mpesa_b2c_timeout_url,
            "mpesa_stk_callback_url": settings.mpesa_stk_callback_url,
            "mno_possession_callback_url": settings.mno_possession_callback_url,
            "mpesa_status_result_url": settings.mpesa_status_result_url,
            "mpesa_status_timeout_url": settings.mpesa_status_timeout_url,
        }

    def pick(inst_field: str | None, global_val: str) -> str:
        return inst_field if inst_field else global_val

    def pick_secret(inst_field: str | None, global_val: str) -> str:
        if inst_field:
            return decrypt_secret(inst_field) or ""
        return global_val

    return InstitutionIntegrationProfile(
        institution_id=institution_id,
        kenya_mode=kenya_mode,
        mpesa_env=pick(record.mpesa_env if record else None, settings.mpesa_env),
        mpesa_consumer_key=pick_secret(record.mpesa_consumer_key if record else None, settings.mpesa_consumer_key),
        mpesa_consumer_secret=pick_secret(
            record.mpesa_consumer_secret if record else None, settings.mpesa_consumer_secret
        ),
        mpesa_shortcode=pick(record.mpesa_shortcode if record else None, settings.mpesa_shortcode),
        mpesa_initiator_name=pick(record.mpesa_initiator_name if record else None, settings.mpesa_initiator_name),
        mpesa_security_credential=pick_secret(
            record.mpesa_security_credential if record else None, settings.mpesa_security_credential
        ),
        mpesa_stk_passkey=pick_secret(record.mpesa_stk_passkey if record else None, settings.mpesa_stk_passkey),
        mpesa_b2c_command_id=pick(
            record.mpesa_b2c_command_id if record else None, settings.mpesa_b2c_command_id
        ),
        mpesa_b2c_result_url=callbacks["mpesa_b2c_result_url"],
        mpesa_b2c_timeout_url=callbacks["mpesa_b2c_timeout_url"],
        mpesa_stk_callback_url=callbacks["mpesa_stk_callback_url"],
        mpesa_status_result_url=callbacks["mpesa_status_result_url"],
        mpesa_status_timeout_url=callbacks["mpesa_status_timeout_url"],
        mno_safaricom_api_url=pick(
            record.mno_safaricom_api_url if record else None, settings.mno_safaricom_api_url
        ),
        mno_safaricom_api_key=pick_secret(
            record.mno_safaricom_api_key if record else None, settings.mno_safaricom_api_key
        ),
        mno_safaricom_dealer_code=pick(
            record.mno_safaricom_dealer_code if record else None, settings.mno_safaricom_dealer_code
        ),
        mno_possession_callback_url=callbacks["mno_possession_callback_url"],
        mno_airtel_api_url=pick(record.mno_airtel_api_url if record else None, settings.mno_airtel_api_url),
        mno_airtel_token_url=pick(record.mno_airtel_token_url if record else None, settings.mno_airtel_token_url),
        mno_airtel_client_id=pick(record.mno_airtel_client_id if record else None, settings.mno_airtel_client_id),
        mno_airtel_client_secret=pick_secret(
            record.mno_airtel_client_secret if record else None, settings.mno_airtel_client_secret
        ),
        broker_api_url=settings.broker_liquidation_api_url,
        broker_api_key=settings.broker_liquidation_api_key,
    )


def upsert_institution_integration(db: Session, institution_id: str, payload: dict) -> InstitutionIntegration:
    institution = db.get(Institution, institution_id)
    if not institution:
        raise ValueError(f"Institution {institution_id} not found")

    record = db.query(InstitutionIntegration).filter(InstitutionIntegration.institution_id == institution_id).first()
    if not record:
        record = InstitutionIntegration(institution_id=institution_id)
        db.add(record)

    secret_fields = {
        "mpesa_consumer_key",
        "mpesa_consumer_secret",
        "mpesa_security_credential",
        "mpesa_stk_passkey",
        "mno_safaricom_api_key",
        "mno_airtel_client_secret",
    }

    for key, value in payload.items():
        if value is None:
            continue
        if key in secret_fields:
            value = encrypt_secret(str(value))
        setattr(record, key, value)

    db.flush()
    return record


def integration_status(db: Session, institution_id: str) -> dict:
    profile = resolve_integration_profile(db, institution_id)
    try:
        callbacks = get_institution_callback_urls(db, institution_id)
    except ValueError:
        callbacks = {}
    return {
        "institution_id": institution_id,
        "kenya_mode": profile.kenya_mode,
        "mpesa_configured": profile.mpesa_configured,
        "mno_safaricom_configured": profile.mno_safaricom_configured,
        "callback_urls": callbacks,
    }
