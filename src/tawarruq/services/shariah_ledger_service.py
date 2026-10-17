"""
Isolated append-only Shariah audit ledger.

All writes go through `append_shariah_entry`. Updates and deletes are blocked at the ORM layer.
Each entry includes a hash chain (previous_hash -> entry_hash) for tamper detection.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tawarruq.enums import ShariahStepId
from tawarruq.models.kenya_flow import ShariahAuditLog
from tawarruq.services.shariah_crypto import GENESIS_HASH, compute_entry_hash, compute_payload_hash


def _latest_entry_hash(db: Session) -> str:
    latest = (
        db.query(ShariahAuditLog)
        .order_by(ShariahAuditLog.timestamp.desc(), ShariahAuditLog.id.desc())
        .first()
    )
    return latest.entry_hash if latest else GENESIS_HASH


def append_shariah_entry(
    db: Session,
    *,
    step_id: ShariahStepId | str,
    entity_type: str,
    entity_id: str,
    actor_from: str,
    actor_to: str,
    payload: dict[str, Any],
    asset_ref_no: str | None = None,
    details: str | None = None,
    verified_at: datetime | None = None,
    mno_receipt_id: str | None = None,
    institution_id: str | None = None,
    transaction_id: str | None = None,
    application_id: str | None = None,
) -> ShariahAuditLog:
    """Append a single immutable Shariah audit record to the ledger."""
    now = datetime.now(UTC)
    payload_hash = compute_payload_hash(payload)
    previous_hash = _latest_entry_hash(db)

    if str(step_id) == ShariahStepId.CONSTRUCTIVE_POSSESSION:
        if not verified_at:
            verified_at = now
        if not mno_receipt_id:
            mno_receipt_id = payload.get("mno_receipt_id") or asset_ref_no
        if not mno_receipt_id:
            raise ValueError("CONSTRUCTIVE_POSSESSION requires MNO receipt ID")

    entry_hash = compute_entry_hash(
        step_id=str(step_id),
        entity_type=entity_type,
        entity_id=entity_id,
        asset_ref_no=asset_ref_no,
        actor_from=actor_from,
        actor_to=actor_to,
        payload_hash=payload_hash,
        verified_at=verified_at,
        mno_receipt_id=mno_receipt_id,
        institution_id=institution_id,
        transaction_id=transaction_id,
        application_id=application_id,
        previous_hash=previous_hash,
        timestamp=now,
    )

    entry = ShariahAuditLog(
        id=str(uuid.uuid4()),
        timestamp=now,
        step_id=str(step_id),
        entity_type=entity_type,
        entity_id=entity_id,
        asset_ref_no=asset_ref_no,
        actor_from=actor_from,
        actor_to=actor_to,
        payload_hash=payload_hash,
        details=details,
        verified_at=verified_at,
        mno_receipt_id=mno_receipt_id,
        institution_id=institution_id,
        transaction_id=transaction_id,
        application_id=application_id,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
    )
    db.add(entry)
    db.flush()
    return entry


def verify_ledger_chain(db: Session, *, institution_id: str | None = None, limit: int = 10_000) -> dict[str, Any]:
    """Verify hash chain integrity for regulatory export / CBK audit."""
    query = db.query(ShariahAuditLog).order_by(ShariahAuditLog.timestamp.asc(), ShariahAuditLog.id.asc())
    if institution_id:
        query = query.filter(ShariahAuditLog.institution_id == institution_id)
    entries = query.limit(limit).all()

    expected_previous = GENESIS_HASH
    broken_at: str | None = None
    for entry in entries:
        if entry.previous_hash != expected_previous:
            broken_at = entry.id
            break
        recomputed = compute_entry_hash(
            step_id=entry.step_id,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            asset_ref_no=entry.asset_ref_no,
            actor_from=entry.actor_from,
            actor_to=entry.actor_to,
            payload_hash=entry.payload_hash,
            verified_at=entry.verified_at,
            mno_receipt_id=entry.mno_receipt_id,
            institution_id=entry.institution_id,
            transaction_id=entry.transaction_id,
            application_id=entry.application_id,
            previous_hash=entry.previous_hash,
            timestamp=entry.timestamp,
        )
        if recomputed != entry.entry_hash:
            broken_at = entry.id
            break
        expected_previous = entry.entry_hash

    return {
        "valid": broken_at is None,
        "entries_checked": len(entries),
        "broken_at_entry_id": broken_at,
        "genesis_hash": GENESIS_HASH,
        "tip_hash": expected_previous if entries else GENESIS_HASH,
    }


def _block_shariah_mutation(mapper, connection, target) -> None:  # noqa: ARG001
    raise IntegrityError(
        "Shariah audit ledger is append-only — updates and deletes are forbidden",
        params=None,
        orig=Exception("append-only violation"),
    )


def register_append_only_guards() -> None:
    if not event.contains(ShariahAuditLog, "before_update", _block_shariah_mutation):
        event.listen(ShariahAuditLog, "before_update", _block_shariah_mutation)
        event.listen(ShariahAuditLog, "before_delete", _block_shariah_mutation)
