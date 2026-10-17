"""Optional mirror of Shariah audit entries to an isolated append-only service."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from tawarruq.config import get_settings
from tawarruq.models.kenya_flow import ShariahAuditLog

logger = logging.getLogger(__name__)


def _serialize_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def mirror_shariah_entry_if_configured(entry: ShariahAuditLog, payload: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.shariah_audit_service_url:
        return

    body = {
        "step_id": entry.step_id,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "actor_from": entry.actor_from,
        "actor_to": entry.actor_to,
        "payload": payload,
        "asset_ref_no": entry.asset_ref_no,
        "details": entry.details,
        "verified_at": _serialize_dt(entry.verified_at),
        "mno_receipt_id": entry.mno_receipt_id,
        "institution_id": entry.institution_id,
        "transaction_id": entry.transaction_id,
        "application_id": entry.application_id,
    }
    url = f"{settings.shariah_audit_service_url.rstrip('/')}/v1/entries"
    headers: dict[str, str] = {}
    if settings.shariah_audit_service_token:
        headers["Authorization"] = f"Bearer {settings.shariah_audit_service_token}"

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, json=body, headers=headers)
            response.raise_for_status()
    except Exception as exc:
        logger.warning("Shariah audit mirror failed: %s", exc)
