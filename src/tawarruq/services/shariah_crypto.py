"""Cryptographic helpers for the Shariah audit ledger."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

GENESIS_HASH = "0" * 64


def _utc_iso(timestamp: datetime) -> str:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    else:
        timestamp = timestamp.astimezone(UTC)
    return timestamp.isoformat()


def compute_payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_entry_hash(
    *,
    step_id: str,
    entity_type: str,
    entity_id: str,
    asset_ref_no: str | None,
    actor_from: str,
    actor_to: str,
    payload_hash: str,
    verified_at: datetime | None,
    mno_receipt_id: str | None,
    institution_id: str | None,
    transaction_id: str | None,
    application_id: str | None,
    previous_hash: str,
    timestamp: datetime,
) -> str:
    body = {
        "timestamp": _utc_iso(timestamp),
        "step_id": step_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "asset_ref_no": asset_ref_no,
        "actor_from": actor_from,
        "actor_to": actor_to,
        "payload_hash": payload_hash,
        "verified_at": _utc_iso(verified_at) if verified_at else None,
        "mno_receipt_id": mno_receipt_id,
        "institution_id": institution_id,
        "transaction_id": transaction_id,
        "application_id": application_id,
        "previous_hash": previous_hash,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
