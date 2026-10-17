"""7-year certificate vault for Sedania source certs and Buruuj legal stamps."""
from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.enums import VaultCertificateKind
from tawarruq.models.execution import CertificateVault


def vault_public_url(vault: CertificateVault) -> str:
    settings = get_settings()
    base = (settings.public_api_base_url or "http://127.0.0.1:8000").rstrip("/")
    prefix = settings.api_prefix.rstrip("/")
    return f"{base}{prefix}/tawarruq/certificates/{vault.id}?token={vault.access_token}"


def store_certificate(
    db: Session,
    execution_id: str,
    institution_id: str,
    application_id: str | None,
    kind: VaultCertificateKind | str,
    certificate_number: str,
    source: str,
    payload: dict[str, Any],
    source_url: str | None = None,
    serial_numbers: list[str] | None = None,
    batch_id: str | None = None,
) -> CertificateVault:
    settings = get_settings()
    years = max(1, int(settings.certificate_retention_years or 7))
    record = CertificateVault(
        execution_id=execution_id,
        institution_id=institution_id,
        application_id=application_id,
        kind=str(kind),
        certificate_number=certificate_number,
        source=source,
        source_url=source_url,
        access_token=secrets.token_urlsafe(24),
        payload_json=json.dumps(payload, default=str),
        serial_numbers_json=json.dumps(serial_numbers) if serial_numbers else None,
        batch_id=batch_id,
        retention_until=datetime.now(UTC) + timedelta(days=365 * years),
    )
    db.add(record)
    db.flush()
    return record


def get_vault_certificate(db: Session, vault_id: str, token: str) -> CertificateVault | None:
    record = db.get(CertificateVault, vault_id)
    if not record or record.access_token != token:
        return None
    return record
