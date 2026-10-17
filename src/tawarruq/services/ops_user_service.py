"""Ops portal password auth, session tokens, and user provisioning."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.enums import ApiKeyRole
from tawarruq.models.kenya_flow import AgentDealer
from tawarruq.models.ops_user import OpsUser

TOKEN_TTL_SECONDS = 60 * 60 * 12  # 12 hours
PBKDF2_ITERATIONS = 120_000


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
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


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
) -> tuple[OpsUser, str]:
    email_norm = email.strip().lower()
    if get_user_by_email(db, email_norm):
        raise ValueError(f"User already exists: {email_norm}")
    if role not in {ApiKeyRole.PLATFORM_ADMIN, ApiKeyRole.AGENT_DEALER} and not institution_id:
        raise ValueError("institution_id is required for bank and SACCO roles")
    bound_dealer_id = _bound_dealer_id(
        db, role=role, institution_id=None, agent_dealer_id=agent_dealer_id
    )
    temp = temporary_password or generate_temporary_password()
    user = OpsUser(
        email=email_norm,
        full_name=full_name.strip(),
        password_hash=hash_password(temp),
        role=role.value,
        institution_id=None if role in {ApiKeyRole.PLATFORM_ADMIN, ApiKeyRole.AGENT_DEALER} else institution_id,
        agent_dealer_id=bound_dealer_id,
        must_change_password=must_change_password,
        active=True,
        created_by_id=created_by_id,
    )
    db.add(user)
    db.flush()
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
    actor_id: str | None = None,
    actor_is_platform_admin: bool = False,
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
        if role == ApiKeyRole.PLATFORM_ADMIN and not actor_is_platform_admin:
            raise ValueError("Only platform admins can assign platform_admin")
        if (
            user.role == ApiKeyRole.PLATFORM_ADMIN.value
            and role != ApiKeyRole.PLATFORM_ADMIN
            and user.active
            and _active_platform_admins(db) <= 1
        ):
            raise ValueError("Cannot demote the last active platform admin")
        if (
            role not in {ApiKeyRole.PLATFORM_ADMIN, ApiKeyRole.AGENT_DEALER}
            and not institution_id
            and not user.institution_id
        ):
            raise ValueError("institution_id is required for bank and SACCO roles")
        user.role = role.value
        if role in {ApiKeyRole.PLATFORM_ADMIN, ApiKeyRole.AGENT_DEALER}:
            user.institution_id = None
            if role == ApiKeyRole.PLATFORM_ADMIN:
                user.agent_dealer_id = None
        elif institution_id:
            user.institution_id = institution_id
        user.agent_dealer_id = _bound_dealer_id(
            db,
            role=role,
            institution_id=user.institution_id,
            agent_dealer_id=agent_dealer_id if role == ApiKeyRole.AGENT_DEALER else None,
        )
    elif institution_id and user.role != ApiKeyRole.PLATFORM_ADMIN.value:
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
    db.flush()
    return user


def reset_ops_password(db: Session, user: OpsUser, *, temporary_password: str | None = None) -> str:
    temp = temporary_password or generate_temporary_password()
    if len(temp) < 8:
        raise ValueError("Temporary password must be at least 8 characters")
    user.password_hash = hash_password(temp)
    user.must_change_password = True
    db.flush()
    return temp


def delete_ops_user(db: Session, user: OpsUser, *, actor_id: str | None = None) -> None:
    if actor_id and user.id == actor_id:
        raise ValueError("You cannot delete your own account")
    if user.role == ApiKeyRole.PLATFORM_ADMIN.value and user.active and _active_platform_admins(db) <= 1:
        raise ValueError("Cannot delete the last active platform admin")
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
