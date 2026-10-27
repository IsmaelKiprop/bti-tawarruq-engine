import hashlib
import hmac
import logging
import secrets
import time

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.enums import ApiKeyRole
from tawarruq.models.integration import ApiKey

logger = logging.getLogger(__name__)

HMAC_HEADER = "X-BTI-Signature"
TIMESTAMP_HEADER = "X-BTI-Timestamp"


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    raw_key = f"bti_{prefix}_{secret}"
    return raw_key, prefix, hash_api_key(raw_key)


def create_api_key(
    db: Session,
    *,
    institution_id: str,
    name: str,
    role: ApiKeyRole = ApiKeyRole.INSTITUTION_OPS,
) -> tuple[ApiKey, str]:
    raw_key, prefix, key_hash = generate_api_key()
    record = ApiKey(
        institution_id=institution_id,
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
        hmac_secret=secrets.token_urlsafe(32),
        reveal_key=raw_key if role == ApiKeyRole.API_CLIENT else None,
        role=role.value,
    )
    db.add(record)
    db.flush()
    return record, raw_key


def validate_api_key(db: Session, raw_key: str) -> ApiKey | None:
    if not raw_key.startswith("bti_"):
        return None
    parts = raw_key.split("_", 2)
    if len(parts) < 3:
        return None
    prefix = parts[1]
    key_hash = hash_api_key(raw_key)
    record = (
        db.query(ApiKey)
        .filter(ApiKey.key_prefix == prefix, ApiKey.key_hash == key_hash, ApiKey.active.is_(True))
        .first()
    )
    return record


def list_api_keys(db: Session, institution_id: str) -> list[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.institution_id == institution_id, ApiKey.active.is_(True)).all()


def sign_sacco_payload(*, hmac_secret: str, timestamp: str, body: bytes) -> str:
    canonical = timestamp.encode() + b"." + body
    return hmac.new(hmac_secret.encode(), canonical, hashlib.sha256).hexdigest()


def _normalize_signature(raw: str) -> str:
    value = raw.strip()
    if value.lower().startswith("sha256="):
        return value.split("=", 1)[1].strip()
    return value


def verify_sacco_hmac(*, hmac_secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    expected = sign_sacco_payload(hmac_secret=hmac_secret, timestamp=timestamp, body=body)
    provided = _normalize_signature(signature)
    return hmac.compare_digest(expected, provided)


def require_sacco_hmac(request: Request, db: Session, body: bytes) -> None:
    """Verify inbound SACCO HMAC when auth is on, or whenever a signature header is sent."""
    settings = get_settings()
    signature = request.headers.get(HMAC_HEADER)
    timestamp = request.headers.get(TIMESTAMP_HEADER)
    auth_method = getattr(request.state, "auth_method", None)

    must_verify = bool(settings.auth_enabled and auth_method == "api_key") or bool(signature)
    if not must_verify:
        return

    if not signature or not timestamp:
        raise HTTPException(
            status_code=401,
            detail="Missing X-BTI-Signature or X-BTI-Timestamp for SACCO execute",
        )

    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid X-BTI-Timestamp") from exc

    skew = abs(int(time.time()) - ts)
    if skew > settings.hmac_max_skew_seconds:
        raise HTTPException(status_code=401, detail="HMAC timestamp is outside the allowed window")

    api_key_id = getattr(request.state, "api_key_id", None)
    record = db.get(ApiKey, api_key_id) if api_key_id else None
    if record is None or not record.hmac_secret:
        raise HTTPException(
            status_code=401,
            detail="API key has no HMAC secret. Create a new key and sign execute requests with it.",
        )
    if not verify_sacco_hmac(hmac_secret=record.hmac_secret, timestamp=timestamp, body=body, signature=signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
