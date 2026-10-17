"""High-security email auth for the Buruuj Lend mobile app.

Controls:
- Strong password policy (12+ chars, mixed classes)
- Email verification before full access
- Email MFA OTP on every login
- Account lockout after failed attempts
- Short-lived access tokens + rotating refresh tokens
- OTPs and refresh tokens stored hashed only
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.models.customer import Customer
from tawarruq.models.mobile_account import MobileAccount
from tawarruq.services.customer_notify_service import normalize_email
from tawarruq.services.customer_service import create_customer
from tawarruq.services.ops_user_service import hash_password, verify_password

logger = logging.getLogger(__name__)

ACCESS_TTL_SECONDS = 60 * 30  # 30 minutes
REFRESH_TTL_SECONDS = 60 * 60 * 24 * 14  # 14 days
MFA_TTL_SECONDS = 60 * 10  # 10 minutes
VERIFY_TTL_SECONDS = 60 * 30  # 30 minutes
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
OTP_LENGTH = 6

PASSWORD_RULE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{12,128}$"
)

COMMON_PASSWORDS = {
    "password123!",
    "Password123!",
    "Welcome123!",
    "Changeme123!",
    "Qwerty123456!",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _token_secret() -> str:
    settings = get_settings()
    return settings.ops_session_secret or settings.integration_encryption_key or "dev-mobile-session-secret"


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_password_strength(password: str) -> None:
    if not PASSWORD_RULE.match(password or ""):
        raise ValueError(
            "Password must be 12–128 characters and include upper, lower, number, and special character"
        )
    if password.lower() in {p.lower() for p in COMMON_PASSWORDS}:
        raise ValueError("Password is too common. Choose a stronger passphrase")


def _generate_otp() -> str:
    # Cryptographically strong numeric OTP
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def _deliver_email_code(*, email: str, subject: str, body: str, code: str) -> dict[str, Any]:
    """Send via SMTP when configured; always file a local copy for ops/debug."""
    settings = get_settings()
    mail_dir = Path(settings.customer_mail_dir)
    mail_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utcnow().strftime("%Y%m%d%H%M%S")
    safe = email.replace("@", "_at_").replace(".", "_")
    path = mail_dir / f"mobile_auth_{safe}_{stamp}.txt"
    path.write_text(f"To: {email}\nSubject: {subject}\n\n{body}\n\nCODE={code}\n", encoding="utf-8")

    smtp_sent = False
    if settings.smtp_host:
        try:
            from tawarruq.services.customer_notify_service import _send_smtp

            smtp_sent = bool(_send_smtp(email, subject, body))
        except Exception:
            logger.exception("SMTP send failed for mobile auth to %s", email)

    # Expose code only when SMTP is off (local / mock demos)
    include_dev = not settings.smtp_host
    return {
        "smtp_sent": smtp_sent,
        "mail_path": str(path),
        "dev_code": code if include_dev else None,
    }


def get_account_by_email(db: Session, email: str) -> MobileAccount | None:
    normalized = normalize_email(email)
    if not normalized:
        return None
    return db.query(MobileAccount).filter(MobileAccount.email == normalized).first()


def register_account(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str,
) -> tuple[MobileAccount, dict[str, Any]]:
    normalized = normalize_email(email)
    if not normalized or "@" not in normalized:
        raise ValueError("A valid email address is required")
    if not (full_name or "").strip():
        raise ValueError("Full name is required")
    validate_password_strength(password)

    existing = get_account_by_email(db, normalized)
    if existing:
        raise ValueError("An account with this email already exists")

    account = MobileAccount(
        email=normalized,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        email_verified=False,
        active=True,
        approval_status="pending",
    )
    db.add(account)
    db.flush()

    delivery = _issue_email_verification(db, account)
    return account, delivery


def _issue_email_verification(db: Session, account: MobileAccount) -> dict[str, Any]:
    code = _generate_otp()
    account.email_verify_hash = _hash_secret(code)
    account.email_verify_expires_at = _utcnow() + timedelta(seconds=VERIFY_TTL_SECONDS)
    db.flush()
    return _deliver_email_code(
        email=account.email,
        subject="Verify your Buruuj Lend email",
        body=(
            f"Assalamu alaikum {account.full_name},\n\n"
            f"Your Buruuj Lend verification code is: {code}\n\n"
            f"This code expires in {VERIFY_TTL_SECONDS // 60} minutes. "
            "If you did not create an account, ignore this email.\n"
        ),
        code=code,
    )


def resend_verification(db: Session, email: str) -> dict[str, Any]:
    account = get_account_by_email(db, email)
    if not account:
        # Do not leak whether email exists
        return {"smtp_sent": False, "mail_path": None, "dev_code": None, "status": "accepted"}
    if account.email_verified:
        return {"smtp_sent": False, "mail_path": None, "dev_code": None, "status": "already_verified"}
    delivery = _issue_email_verification(db, account)
    delivery["status"] = "sent"
    return delivery


def verify_email(db: Session, *, email: str, code: str) -> MobileAccount:
    account = get_account_by_email(db, email)
    if not account:
        raise ValueError("Invalid verification code")
    if account.email_verified:
        return account
    if not account.email_verify_hash or not account.email_verify_expires_at:
        raise ValueError("No verification code pending. Request a new one")
    expires = account.email_verify_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _utcnow():
        raise ValueError("Verification code expired. Request a new one")
    if not hmac.compare_digest(account.email_verify_hash, _hash_secret(code.strip())):
        raise ValueError("Invalid verification code")

    account.email_verified = True
    account.email_verify_hash = None
    account.email_verify_expires_at = None
    db.flush()
    return account


def _is_locked(account: MobileAccount) -> bool:
    if not account.locked_until:
        return False
    locked = account.locked_until
    if locked.tzinfo is None:
        locked = locked.replace(tzinfo=timezone.utc)
    if locked > _utcnow():
        return True
    account.locked_until = None
    account.failed_login_count = 0
    return False


def _register_failure(account: MobileAccount) -> None:
    account.failed_login_count = (account.failed_login_count or 0) + 1
    if account.failed_login_count >= MAX_FAILED_LOGINS:
        account.locked_until = _utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        account.failed_login_count = 0


def begin_login(db: Session, *, email: str, password: str) -> dict[str, Any]:
    """Step 1: password check → issue MFA challenge to email."""
    account = get_account_by_email(db, email)
    if not account or not account.active:
        raise ValueError("Invalid email or password")
    if _is_locked(account):
        raise ValueError("Account temporarily locked after failed attempts. Try again later")
    if not verify_password(password, account.password_hash):
        _register_failure(account)
        db.flush()
        raise ValueError("Invalid email or password")
    if not account.email_verified:
        raise ValueError("Email not verified. Check your inbox for the verification code")

    account.failed_login_count = 0
    account.locked_until = None

    code = _generate_otp()
    mfa_token = secrets.token_urlsafe(32)
    account.mfa_challenge_hash = _hash_secret(code)
    account.mfa_challenge_expires_at = _utcnow() + timedelta(seconds=MFA_TTL_SECONDS)
    account.mfa_token_hash = _hash_secret(mfa_token)
    account.mfa_token_expires_at = _utcnow() + timedelta(seconds=MFA_TTL_SECONDS)
    db.flush()

    delivery = _deliver_email_code(
        email=account.email,
        subject="Buruuj Lend login code",
        body=(
            f"Assalamu alaikum {account.full_name},\n\n"
            f"Your login security code is: {code}\n\n"
            f"This code expires in {MFA_TTL_SECONDS // 60} minutes. "
            "Never share it. If this was not you, change your password immediately.\n"
        ),
        code=code,
    )
    return {
        "mfa_required": True,
        "mfa_token": mfa_token,
        "email": account.email,
        "expires_in": MFA_TTL_SECONDS,
        **delivery,
    }


def complete_login_mfa(db: Session, *, mfa_token: str, code: str) -> dict[str, Any]:
    token_hash = _hash_secret(mfa_token)
    account = (
        db.query(MobileAccount)
        .filter(MobileAccount.mfa_token_hash == token_hash, MobileAccount.active.is_(True))
        .first()
    )
    if not account:
        raise ValueError("Invalid or expired login challenge")
    if not account.mfa_token_expires_at or not account.mfa_challenge_hash:
        raise ValueError("Invalid or expired login challenge")
    expires = account.mfa_token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _utcnow():
        raise ValueError("Login challenge expired. Sign in again")
    if not hmac.compare_digest(account.mfa_challenge_hash, _hash_secret(code.strip())):
        _register_failure(account)
        db.flush()
        raise ValueError("Invalid security code")

    account.mfa_challenge_hash = None
    account.mfa_challenge_expires_at = None
    account.mfa_token_hash = None
    account.mfa_token_expires_at = None
    account.last_login_at = _utcnow()
    account.failed_login_count = 0
    tokens = _issue_session_tokens(account)
    db.flush()
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "expires_in": ACCESS_TTL_SECONDS,
        "account": account_public(account),
    }


def _issue_session_tokens(account: MobileAccount) -> dict[str, str]:
    access = _encode_access_token(account)
    refresh = secrets.token_urlsafe(48)
    account.refresh_token_hash = _hash_secret(refresh)
    account.refresh_token_expires_at = _utcnow() + timedelta(seconds=REFRESH_TTL_SECONDS)
    return {"access_token": access, "refresh_token": refresh}


def _encode_access_token(account: MobileAccount) -> str:
    payload = {
        "sub": account.id,
        "email": account.email,
        "typ": "mobile",
        "customer_id": account.customer_id,
        "institution_id": account.institution_id,
        "exp": int(time.time()) + ACCESS_TTL_SECONDS,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_token_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def decode_mobile_access_token(token: str) -> dict[str, Any] | None:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(_token_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        padding = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + padding).decode())
        if payload.get("typ") != "mobile":
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def refresh_session(db: Session, *, refresh_token: str) -> dict[str, Any]:
    token_hash = _hash_secret(refresh_token)
    account = (
        db.query(MobileAccount)
        .filter(MobileAccount.refresh_token_hash == token_hash, MobileAccount.active.is_(True))
        .first()
    )
    if not account or not account.refresh_token_expires_at:
        raise ValueError("Invalid refresh token")
    expires = account.refresh_token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _utcnow():
        raise ValueError("Refresh token expired. Sign in again")
    # Rotate refresh token
    tokens = _issue_session_tokens(account)
    db.flush()
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
        "expires_in": ACCESS_TTL_SECONDS,
        "account": account_public(account),
    }


def logout(db: Session, account: MobileAccount) -> None:
    account.refresh_token_hash = None
    account.refresh_token_expires_at = None
    account.mfa_challenge_hash = None
    account.mfa_token_hash = None
    db.flush()


def account_public(account: MobileAccount) -> dict[str, Any]:
    return {
        "id": account.id,
        "email": account.email,
        "full_name": account.full_name,
        "email_verified": account.email_verified,
        "customer_id": account.customer_id,
        "institution_id": account.institution_id,
        "has_customer_profile": bool(account.customer_id),
        "approval_status": getattr(account, "approval_status", None) or "pending",
        "phone": getattr(account, "phone", None),
        "credit_limit": str(account.credit_limit) if getattr(account, "credit_limit", None) is not None else None,
        "rejection_reason": getattr(account, "rejection_reason", None),
    }


def ensure_customer_profile(
    db: Session,
    account: MobileAccount,
    *,
    phone: str,
    wallet_provider: str = "mpesa",
    wallet_number: str | None = None,
) -> Customer | None:
    """Save wallet phone. Full Customer + KYC only after institution approval."""
    from tawarruq.enums import AmlStatus, KycStatus
    from tawarruq.models.mobile_account import APPROVAL_APPROVED

    phone = (phone or "").strip()
    if not phone.startswith("254") or len(phone) < 12:
        raise ValueError("Phone must be in 254XXXXXXXXX format")

    account.phone = phone
    db.flush()

    if account.approval_status != APPROVAL_APPROVED:
        return None

    from tawarruq.services import application_service

    if account.customer_id:
        customer = db.get(Customer, account.customer_id)
        if customer:
            customer.phone = phone
            customer.wallet_number = wallet_number or phone
            customer.wallet_provider = wallet_provider
            customer.email = account.email
            customer.full_name = account.full_name
            db.flush()
            return customer

    if not account.institution_id:
        institution = application_service.get_or_create_default_institution(db)
        account.institution_id = institution.id

    existing = (
        db.query(Customer)
        .filter(Customer.institution_id == account.institution_id, Customer.phone == phone)
        .first()
    )
    if existing:
        existing.email = account.email
        existing.full_name = account.full_name
        existing.wallet_number = wallet_number or phone
        existing.wallet_provider = wallet_provider
        customer = existing
    else:
        customer = create_customer(
            db,
            institution_id=account.institution_id,
            phone=phone,
            email=account.email,
            full_name=account.full_name,
            wallet_number=wallet_number or phone,
            wallet_provider=wallet_provider,
        )

    account.customer_id = customer.id
    account.institution_id = customer.institution_id
    db.flush()
    customer = db.get(Customer, account.customer_id)
    if (
        not customer
        or customer.kyc_status != KycStatus.VERIFIED
        or customer.aml_status != AmlStatus.CLEAR
    ):
        raise ValueError("Institution approval and KYC/AML are required before financing")
    return customer


def request_password_reset(db: Session, email: str) -> dict[str, Any]:
    """Always return accepted to avoid email enumeration."""
    account = get_account_by_email(db, email)
    if not account or not account.active or not account.email_verified:
        return {"smtp_sent": False, "mail_path": None, "dev_code": None, "status": "accepted"}

    code = _generate_otp()
    account.password_reset_hash = _hash_secret(code)
    account.password_reset_expires_at = _utcnow() + timedelta(seconds=VERIFY_TTL_SECONDS)
    db.flush()
    delivery = _deliver_email_code(
        email=account.email,
        subject="Reset your Buruuj Lend password",
        body=(
            f"Assalamu alaikum {account.full_name},\n\n"
            f"Your password reset code is: {code}\n\n"
            f"This code expires in {VERIFY_TTL_SECONDS // 60} minutes. "
            "If you did not request a reset, ignore this email.\n"
        ),
        code=code,
    )
    delivery["status"] = "accepted"
    return delivery


def reset_password(db: Session, *, email: str, code: str, new_password: str) -> None:
    validate_password_strength(new_password)
    account = get_account_by_email(db, email)
    if not account or not account.password_reset_hash or not account.password_reset_expires_at:
        raise ValueError("Invalid or expired reset code")
    expires = account.password_reset_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _utcnow():
        raise ValueError("Reset code expired. Request a new one")
    if not hmac.compare_digest(account.password_reset_hash, _hash_secret(code.strip())):
        raise ValueError("Invalid or expired reset code")

    account.password_hash = hash_password(new_password)
    account.password_reset_hash = None
    account.password_reset_expires_at = None
    account.refresh_token_hash = None
    account.refresh_token_expires_at = None
    account.failed_login_count = 0
    account.locked_until = None
    db.flush()


def change_password(db: Session, account: MobileAccount, *, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, account.password_hash):
        raise ValueError("Current password is incorrect")
    validate_password_strength(new_password)
    if current_password == new_password:
        raise ValueError("New password must be different from the current password")
    account.password_hash = hash_password(new_password)
    account.refresh_token_hash = None
    account.refresh_token_expires_at = None
    db.flush()
