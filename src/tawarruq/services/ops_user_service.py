"""Ops portal password auth, session tokens, and user provisioning."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.enums import ApiKeyRole
from tawarruq.models.kenya_flow import AgentDealer
from tawarruq.enums import AuditActor
from tawarruq.models.ops_user import OpsUser
from tawarruq.services.audit_service import log_audit
from tawarruq.services.rbac import PLATFORM_SCOPED_ROLES, PORTAL_ASSIGNABLE_ROLES

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12 hours
MFA_CHALLENGE_TTL_SECONDS = 60 * 5
PBKDF2_ITERATIONS = 120_000
_UNSET = object()


def _session_secret() -> str:
    settings = get_settings()
    return settings.ops_session_secret or settings.integration_encryption_key or "dev-ops-session-secret"


def hash_password(password: str, *, salt_hex: str | None = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = password_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def generate_temporary_password(length: int = 12) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def deliver_ops_invite_email(
    *,
    user: OpsUser,
    temporary_password: str,
    kind: str = "invite",
) -> dict[str, Any]:
    """Email a temporary password via SMTP (and always file a local copy).

    When SMTP is configured and the send succeeds, the temporary password is
    withheld from API responses (``expose_password=False``). When SMTP is off
    or fails, the password is returned so the admin can share it out of band.
    """
    settings = get_settings()
    portal = (settings.portal_public_url or "http://127.0.0.1:5173").rstrip("/")
    is_reset = kind == "reset"
    subject = (
        "BTI Tawarruq ops — password reset"
        if is_reset
        else "You are invited to the BTI Tawarruq ops portal"
    )
    action = "Your password was reset by an administrator." if is_reset else "You have been invited to the BTI Tawarruq ops portal."
    body = (
        f"Assalamu alaikum {user.full_name},\n\n"
        f"{action}\n\n"
        f"Portal: {portal}\n"
        f"Email: {user.email}\n"
        f"Temporary password: {temporary_password}\n\n"
        "On first sign-in you must change this password before you can use the portal.\n"
        "Do not share this password. If you did not expect this email, contact your administrator.\n\n"
        "Buruuj Fintech — BTI Tawarruq Engine\n"
    )

    mail_path: str | None = None
    try:
        mail_dir = settings.customer_mail_path / "ops_invites"
        mail_dir.mkdir(parents=True, exist_ok=True)
        safe = user.email.replace("@", "_at_").replace(".", "_")
        path = mail_dir / f"{safe}.txt"
        path.write_text(f"To: {user.email}\nSubject: {subject}\n\n{body}", encoding="utf-8")
        mail_path = str(path)
    except Exception:
        logger.exception("Could not file ops invite mail for %s", user.email)

    smtp_sent = False
    if settings.smtp_host:
        try:
            from tawarruq.services.customer_notify_service import _send_smtp

            smtp_sent = bool(_send_smtp(user.email, subject, body))
        except Exception:
            logger.exception("SMTP send failed for ops invite to %s", user.email)

    return {
        "smtp_sent": smtp_sent,
        "mail_path": mail_path,
        # Never echo the password in the API when SMTP delivered it.
        "expose_password": not smtp_sent,
        "kind": kind,
    }


def create_session_token(user: OpsUser) -> str:
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "institution_id": user.institution_id,
        "must_change_password": user.must_change_password,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_session_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def decode_session_token(token: str) -> dict[str, Any] | None:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(_session_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        padding = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + padding).decode())
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if payload.get("typ") == "mfa":
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def create_mfa_challenge_token(user: OpsUser) -> str:
    payload = {
        "sub": user.id,
        "typ": "mfa",
        "email": user.email,
        "exp": int(time.time()) + MFA_CHALLENGE_TTL_SECONDS,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_session_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def decode_mfa_challenge_token(token: str) -> dict[str, Any] | None:
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(_session_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        padding = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + padding).decode())
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if payload.get("typ") != "mfa":
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def begin_mfa_enroll(user: OpsUser) -> tuple[str, str]:
    from tawarruq.services.totp_service import generate_totp_secret, otpauth_url

    secret = generate_totp_secret()
    user.mfa_secret = secret
    user.mfa_method = "totp"
    user.mfa_enabled = False
    return secret, otpauth_url(secret, user.email)


def confirm_mfa_enroll(user: OpsUser, code: str) -> None:
    from tawarruq.services.totp_service import verify_totp

    if not user.mfa_secret:
        raise ValueError("Start MFA enrollment first")
    if not verify_totp(user.mfa_secret, code):
        raise ValueError("Invalid authenticator code")
    user.mfa_method = "totp"
    user.mfa_enabled = True


EMAIL_OTP_TTL_SECONDS = 10 * 60
_email_otp_store: dict[str, tuple[str, float]] = {}


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def issue_email_otp(user: OpsUser, *, purpose: str = "login") -> dict[str, Any]:
    """Generate a 6-digit email code, file a local copy, and SMTP-send when configured."""
    from pathlib import Path

    code = f"{secrets.randbelow(1_000_000):06d}"
    _email_otp_store[user.id] = (_hash_otp(code), time.time() + EMAIL_OTP_TTL_SECONDS)

    settings = get_settings()
    subject = "Buruuj Ops portal verification code"
    body = (
        f"Hello {user.full_name},\n\n"
        f"Your one-time code for {purpose} is: {code}\n\n"
        f"It expires in {EMAIL_OTP_TTL_SECONDS // 60} minutes.\n"
        "If you did not request this, ignore this message.\n"
    )
    mail_dir = Path(settings.customer_mail_dir) / "ops_mfa"
    mail_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d%H%M%S")
    safe = user.email.replace("@", "_at_").replace(".", "_")
    path = mail_dir / f"mfa_{safe}_{stamp}.txt"
    path.write_text(f"To: {user.email}\nSubject: {subject}\n\n{body}\n", encoding="utf-8")

    smtp_sent = False
    if settings.smtp_host:
        try:
            from tawarruq.services.customer_notify_service import _send_smtp

            smtp_sent = bool(_send_smtp(user.email, subject, body))
        except Exception:
            logger.exception("SMTP send failed for ops MFA to %s", user.email)

    return {
        "smtp_sent": smtp_sent,
        "mail_path": str(path),
        "dev_code": None if settings.smtp_host else code,
        "email": user.email,
    }


def verify_email_otp(user: OpsUser, code: str) -> bool:
    entry = _email_otp_store.get(user.id)
    if not entry:
        return False
    digest, expires = entry
    if time.time() > expires:
        _email_otp_store.pop(user.id, None)
        return False
    if not hmac.compare_digest(digest, _hash_otp(code.strip())):
        return False
    _email_otp_store.pop(user.id, None)
    return True


def confirm_email_mfa_enroll(user: OpsUser, code: str) -> None:
    if not verify_email_otp(user, code):
        raise ValueError("Invalid or expired email code")
    user.mfa_secret = None
    user.mfa_method = "email"
    user.mfa_enabled = True


def enable_email_mfa(user: OpsUser) -> None:
    """Turn on email MFA without an enrollment challenge — codes are gated at login."""
    user.mfa_secret = None
    user.mfa_method = "email"
    user.mfa_enabled = True
    _email_otp_store.pop(user.id, None)


def enable_totp_mfa(user: OpsUser) -> None:
    """Finish authenticator setup after the secret was issued — verification happens at login."""
    if not user.mfa_secret:
        raise ValueError("Start authenticator enrollment first")
    user.mfa_method = "totp"
    user.mfa_enabled = True


def disable_mfa(user: OpsUser, *, password: str) -> None:
    if not verify_password(password, user.password_hash):
        raise ValueError("Current password is incorrect")
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_method = None
    _email_otp_store.pop(user.id, None)


def user_mfa_method(user: OpsUser) -> str | None:
    if not user.mfa_enabled:
        return None
    if user.mfa_method in ("totp", "email"):
        return user.mfa_method
    return "totp" if user.mfa_secret else "email"


def get_user_by_email(db: Session, email: str) -> OpsUser | None:
    return db.query(OpsUser).filter(OpsUser.email == email.strip().lower()).first()


def authenticate_user(db: Session, email: str, password: str) -> OpsUser | None:
    user = get_user_by_email(db, email)
    if not user or not user.active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def _bound_dealer_id(
    db: Session,
    *,
    role: ApiKeyRole,
    institution_id: str | None,
    agent_dealer_id: str | None,
) -> str | None:
    if role != ApiKeyRole.AGENT_DEALER:
        return None
    if not agent_dealer_id:
        raise ValueError("agent_dealer_id is required for agent_dealer users")
    dealer = db.get(AgentDealer, agent_dealer_id)
    if not dealer:
        raise ValueError("Agent dealer not found")
    if institution_id and dealer.institution_id and dealer.institution_id != institution_id:
        raise ValueError("Dealer does not belong to this institution")
    return dealer.id


def create_ops_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    role: ApiKeyRole,
    institution_id: str | None,
    temporary_password: str | None = None,
    created_by_id: str | None = None,
    must_change_password: bool = True,
    agent_dealer_id: str | None = None,
    approval_limit_amount=None,
) -> tuple[OpsUser, str]:
    email_norm = email.strip().lower()
    if get_user_by_email(db, email_norm):
        raise ValueError(f"User already exists: {email_norm}")
    if role not in PORTAL_ASSIGNABLE_ROLES:
        raise ValueError(f"Role {role.value} cannot be used for portal logins")
    # Reconciler may be BTI-wide (null institution) or tenant-scoped.
    if role not in PLATFORM_SCOPED_ROLES and role != ApiKeyRole.RECONCILER and not institution_id:
        raise ValueError("institution_id is required for bank and SACCO roles")
    if role == ApiKeyRole.RECONCILER and not institution_id:
        # BTI-wide reconciler — allowed
        pass
    bound_dealer_id = _bound_dealer_id(
        db, role=role, institution_id=None, agent_dealer_id=agent_dealer_id
    )
    temp = temporary_password or generate_temporary_password()
    clear_institution = role in PLATFORM_SCOPED_ROLES
    user = OpsUser(
        email=email_norm,
        full_name=full_name.strip(),
        password_hash=hash_password(temp),
        role=role.value,
        institution_id=None if clear_institution else institution_id,
        agent_dealer_id=bound_dealer_id,
        must_change_password=must_change_password,
        active=True,
        created_by_id=created_by_id,
        approval_limit_amount=approval_limit_amount,
    )
    db.add(user)
    db.flush()
    log_audit(
        db,
        entity_type="ops_user",
        entity_id=user.id,
        actor=AuditActor.HUMAN,
        action="ops_user.created",
        details=f"email={user.email}, role={user.role}, by={created_by_id or 'system'}",
        institution_id=user.institution_id,
        actor_user_id=created_by_id,
        action_group="users",
    )
    return user, temp


def change_password(db: Session, user: OpsUser, *, current_password: str, new_password: str) -> OpsUser:
    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect")
    if len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters")
    if new_password == current_password:
        raise ValueError("New password must be different from the current password")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.flush()
    return user


def list_ops_users(db: Session, *, institution_id: str | None = None) -> list[OpsUser]:
    query = db.query(OpsUser).order_by(OpsUser.created_at.desc())
    if institution_id:
        query = query.filter(
            or_(
                OpsUser.institution_id == institution_id,
                OpsUser.role == ApiKeyRole.AGENT_DEALER.value,
            )
        )
    return query.all()


def _active_platform_admins(db: Session) -> int:
    return (
        db.query(OpsUser)
        .filter(OpsUser.role == ApiKeyRole.PLATFORM_ADMIN.value, OpsUser.active.is_(True))
        .count()
    )


def _clean_optional_text(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:max_len]


def update_ops_user(
    db: Session,
    user: OpsUser,
    *,
    full_name: str | None = None,
    email: str | None = None,
    role: ApiKeyRole | None = None,
    institution_id: str | None = None,
    agent_dealer_id: str | None = None,
    active: bool | None = None,
    approval_limit_amount=_UNSET,
    job_title=_UNSET,
    department=_UNSET,
    employee_number=_UNSET,
    phone=_UNSET,
    office=_UNSET,
    actor_id: str | None = None,
    actor_is_platform_admin: bool = False,
    audit_action: str = "ops_user.updated",
) -> OpsUser:
    if email is not None:
        email_norm = email.strip().lower()
        existing = get_user_by_email(db, email_norm)
        if existing and existing.id != user.id:
            raise ValueError(f"User already exists: {email_norm}")
        user.email = email_norm
    if full_name is not None:
        user.full_name = full_name.strip()
    if role is not None:
        if role not in PORTAL_ASSIGNABLE_ROLES:
            raise ValueError(f"Role {role.value} cannot be used for portal logins")
        from tawarruq.services.rbac import BTI_INTERNAL_ROLES

        if role in BTI_INTERNAL_ROLES and not actor_is_platform_admin:
            raise ValueError("Only platform admins can assign BTI internal roles")
        if (
            user.role == ApiKeyRole.PLATFORM_ADMIN.value
            and role != ApiKeyRole.PLATFORM_ADMIN
            and user.active
            and _active_platform_admins(db) <= 1
        ):
            raise ValueError("Cannot demote the last active platform admin")
        if (
            role not in PLATFORM_SCOPED_ROLES
            and role != ApiKeyRole.RECONCILER
            and not institution_id
            and not user.institution_id
        ):
            raise ValueError("institution_id is required for bank and SACCO roles")
        user.role = role.value
        if role in PLATFORM_SCOPED_ROLES:
            user.institution_id = None
            if role != ApiKeyRole.AGENT_DEALER:
                user.agent_dealer_id = None
        elif institution_id is not None:
            user.institution_id = institution_id
        user.agent_dealer_id = _bound_dealer_id(
            db,
            role=role,
            institution_id=user.institution_id,
            agent_dealer_id=agent_dealer_id if role == ApiKeyRole.AGENT_DEALER else None,
        )
    elif institution_id and user.role not in {r.value for r in PLATFORM_SCOPED_ROLES}:
        user.institution_id = institution_id
    if role is None and agent_dealer_id is not None and user.role == ApiKeyRole.AGENT_DEALER.value:
        user.agent_dealer_id = _bound_dealer_id(
            db,
            role=ApiKeyRole.AGENT_DEALER,
            institution_id=user.institution_id,
            agent_dealer_id=agent_dealer_id,
        )
    if active is not None:
        if actor_id and user.id == actor_id and not active:
            raise ValueError("You cannot deactivate your own account")
        if (
            not active
            and user.role == ApiKeyRole.PLATFORM_ADMIN.value
            and user.active
            and _active_platform_admins(db) <= 1
        ):
            raise ValueError("Cannot deactivate the last active platform admin")
        user.active = active
    if approval_limit_amount is not _UNSET:
        user.approval_limit_amount = approval_limit_amount
    if job_title is not _UNSET:
        user.job_title = _clean_optional_text(job_title, max_len=128)
    if department is not _UNSET:
        user.department = _clean_optional_text(department, max_len=128)
    if employee_number is not _UNSET:
        user.employee_number = _clean_optional_text(employee_number, max_len=64)
    if phone is not _UNSET:
        user.phone = _clean_optional_text(phone, max_len=64)
    if office is not _UNSET:
        user.office = _clean_optional_text(office, max_len=128)
    db.flush()
    log_audit(
        db,
        entity_type="ops_user",
        entity_id=user.id,
        actor=AuditActor.HUMAN,
        action=audit_action,
        details=(
            f"email={user.email}, role={user.role}, active={user.active}, "
            f"job_title={user.job_title or '—'}, department={user.department or '—'}, by={actor_id or 'system'}"
        ),
        institution_id=user.institution_id,
        actor_user_id=actor_id,
        action_group="users",
    )
    return user


def reset_ops_password(db: Session, user: OpsUser, *, temporary_password: str | None = None) -> str:
    temp = temporary_password or generate_temporary_password()
    if len(temp) < 8:
        raise ValueError("Temporary password must be at least 8 characters")
    user.password_hash = hash_password(temp)
    user.must_change_password = True
    db.flush()
    log_audit(
        db,
        entity_type="ops_user",
        entity_id=user.id,
        actor=AuditActor.HUMAN,
        action="ops_user.password_reset",
        details=f"email={user.email}",
        institution_id=user.institution_id,
        action_group="users",
    )
    return temp


def delete_ops_user(db: Session, user: OpsUser, *, actor_id: str | None = None) -> None:
    if actor_id and user.id == actor_id:
        raise ValueError("You cannot delete your own account")
    if user.role == ApiKeyRole.PLATFORM_ADMIN.value and user.active and _active_platform_admins(db) <= 1:
        raise ValueError("Cannot delete the last active platform admin")
    log_audit(
        db,
        entity_type="ops_user",
        entity_id=user.id,
        actor=AuditActor.HUMAN,
        action="ops_user.deleted",
        details=f"email={user.email}, role={user.role}, by={actor_id or 'system'}",
        institution_id=user.institution_id,
        actor_user_id=actor_id,
        action_group="users",
    )
    db.delete(user)
    db.flush()


def ensure_bootstrap_admin(db: Session) -> OpsUser | None:
    """Create default platform admin when AUTH_ENABLED and no users exist."""
    settings = get_settings()
    if not settings.auth_enabled:
        return None
    if db.query(OpsUser).count() > 0:
        return None
    email = (settings.ops_bootstrap_admin_email or "admin@bti.local").strip().lower()
    password = settings.ops_bootstrap_admin_password or "ChangeMeNow!123"
    user, _ = create_ops_user(
        db,
        email=email,
        full_name="Platform Admin",
        role=ApiKeyRole.PLATFORM_ADMIN,
        institution_id=None,
        temporary_password=password,
        must_change_password=True,
    )
    return user
