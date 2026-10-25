"""Idempotent seed of BTI users-doc roles for portal (and one API client key).

Safe for production: never overwrites existing users; writes credentials file only
for newly created accounts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from tawarruq.config import ENGINE_ROOT, get_settings
from tawarruq.enums import ApiKeyRole
from tawarruq.models.institution import Institution
from tawarruq.services.auth_service import create_api_key, list_api_keys
from tawarruq.services.ops_user_service import (
    create_ops_user,
    delete_ops_user,
    ensure_bootstrap_admin,
    get_user_by_email,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeededCredential:
    kind: str  # user | api_key
    email_or_name: str
    role: str
    secret: str
    created: bool


def seed_ops_role_catalogue(db: Session) -> list[SeededCredential]:
    """Create missing portal users for every MVP role (+ api_client key).

    Controlled by OPS_SEED_USERS (default true). Requires AUTH_ENABLED for portal users
    to matter; still runs when auth is off so DBs stay populated for go-live.
    """
    settings = get_settings()
    if not settings.ops_seed_users:
        logger.info("OPS_SEED_USERS=false — skipping role catalogue seed")
        return []

    domain = (settings.ops_seed_email_domain or "buruujfintech.com").strip().lower()
    password = settings.ops_seed_password or "BuruujSeed2026!"
    if len(password) < 8:
        raise ValueError("OPS_SEED_PASSWORD must be at least 8 characters")

    institution = (
        db.query(Institution).filter(Institution.code == "MWALIMU").first()
        or db.query(Institution).order_by(Institution.created_at.asc()).first()
    )
    if not institution:
        from tawarruq.services.application_service import get_or_create_default_institution

        institution = get_or_create_default_institution(db)

    results: list[SeededCredential] = []

    # Platform admin: bootstrap helper (AUTH_ENABLED) or create/find explicitly for prod seed.
    admin = ensure_bootstrap_admin(db)
    bootstrap_email = (settings.ops_bootstrap_admin_email or f"admin@{domain}").strip().lower()
    bootstrap_password = settings.ops_bootstrap_admin_password or password
    if admin:
        results.append(
            SeededCredential(
                kind="user",
                email_or_name=admin.email,
                role=ApiKeyRole.PLATFORM_ADMIN.value,
                secret=bootstrap_password,
                created=True,
            )
        )
    else:
        existing_admin = get_user_by_email(db, bootstrap_email)
        if existing_admin:
            results.append(
                SeededCredential(
                    kind="user",
                    email_or_name=existing_admin.email,
                    role=existing_admin.role,
                    secret="(existing — password unchanged)",
                    created=False,
                )
            )
        else:
            user, temp = create_ops_user(
                db,
                email=bootstrap_email,
                full_name="Site Admin" if settings.is_onprem else "BTI Platform Super Admin",
                role=ApiKeyRole.PLATFORM_ADMIN,
                institution_id=None,
                temporary_password=bootstrap_password,
                must_change_password=True,
            )
            results.append(
                SeededCredential(
                    kind="user",
                    email_or_name=user.email,
                    role=user.role,
                    secret=temp,
                    created=True,
                )
            )

    for local in ("readonly", "dealer"):
        extra = get_user_by_email(db, f"{local}@{domain}")
        if extra:
            delete_ops_user(db, extra)
            logger.info("Removed extra seed login %s", extra.email)

    if settings.is_onprem:
        catalogue: list[tuple[str, str, ApiKeyRole, str | None, str | None]] = [
            ("fi.admin", "Site Administrator", ApiKeyRole.INSTITUTION_ADMIN, institution.id, None),
            ("fi.ops", "Operations Officer", ApiKeyRole.INSTITUTION_OPS, institution.id, None),
            ("fi.approver", "Approver", ApiKeyRole.FI_APPROVER, institution.id, None),
            ("shariah", "Shariah Audit Officer", ApiKeyRole.SHARIAH_OFFICER, institution.id, None),
            ("fi.reconciler", "Reconciliation Officer", ApiKeyRole.RECONCILER, institution.id, None),
        ]
    else:
        catalogue = [
            ("bti.ops", "BTI Tawarruq Operations", ApiKeyRole.BTI_OPS, None, None),
            ("bti.finance", "BTI Finance Billing", ApiKeyRole.BTI_FINANCE, None, None),
            ("fi.admin", "FI Administrator", ApiKeyRole.INSTITUTION_ADMIN, institution.id, None),
            ("fi.ops", "FI Operations Officer", ApiKeyRole.INSTITUTION_OPS, institution.id, None),
            ("fi.approver", "FI Approver", ApiKeyRole.FI_APPROVER, institution.id, None),
            ("shariah", "Shariah Audit Officer", ApiKeyRole.SHARIAH_OFFICER, institution.id, None),
            ("reconciler", "BTI Reconciliation Officer", ApiKeyRole.RECONCILER, None, None),
            ("fi.reconciler", "FI Reconciliation Officer", ApiKeyRole.RECONCILER, institution.id, None),
        ]

    for local, full_name, role, institution_id, agent_dealer_id in catalogue:
        email = f"{local}@{domain}"
        existing = get_user_by_email(db, email)
        if existing:
            results.append(
                SeededCredential(
                    kind="user",
                    email_or_name=email,
                    role=existing.role,
                    secret="(existing — password unchanged)",
                    created=False,
                )
            )
            continue
        user, temp = create_ops_user(
            db,
            email=email,
            full_name=full_name,
            role=role,
            institution_id=institution_id,
            agent_dealer_id=agent_dealer_id,
            temporary_password=password,
            must_change_password=True,
        )
        results.append(
            SeededCredential(
                kind="user",
                email_or_name=user.email,
                role=user.role,
                secret=temp,
                created=True,
            )
        )

    # Institution API client (machine identity)
    existing_keys = list_api_keys(db, institution.id)
    api_key_name = "seed-api-client"
    if any(k.name == api_key_name for k in existing_keys):
        results.append(
            SeededCredential(
                kind="api_key",
                email_or_name=api_key_name,
                role=ApiKeyRole.API_CLIENT.value,
                secret="(existing — key not reissued)",
                created=False,
            )
        )
    else:
        record, raw = create_api_key(
            db,
            institution_id=institution.id,
            name=api_key_name,
            role=ApiKeyRole.API_CLIENT,
        )
        results.append(
            SeededCredential(
                kind="api_key",
                email_or_name=f"{record.name} ({record.key_prefix}…)",
                role=record.role,
                secret=raw,
                created=True,
            )
        )

    created = [r for r in results if r.created]
    if created:
        _write_credentials_file(created, institution_code=institution.code)
        for row in created:
            logger.warning(
                "Seeded %s %s role=%s — change password / rotate key before sharing widely",
                row.kind,
                row.email_or_name,
                row.role,
            )
    else:
        logger.info("Ops role catalogue already present — no new users created")

    return results


def _write_credentials_file(rows: list[SeededCredential], *, institution_code: str) -> Path:
    out_dir = ENGINE_ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ops_seed_credentials.txt"
    lines = [
        "# Newly seeded credentials (append-only). Rotate in production.",
        f"# Institution: {institution_code}",
        "",
    ]
    for row in rows:
        lines.append(f"{row.kind}\t{row.email_or_name}\t{row.role}\t{row.secret}")
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n\n")
    logger.warning("Wrote new seed credentials to %s", path)
    return path
