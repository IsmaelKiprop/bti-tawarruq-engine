"""Match commodity confirmations to settlement / disbursement records."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, joinedload

from tawarruq.enums import AuditActor, TransactionStatus
from tawarruq.models.controls import ReconciliationItem
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.audit_service import log_audit

TWOPLACES = Decimal("0.01")


def _amounts(txn: CommodityTransaction) -> tuple[Decimal, Decimal]:
    expected = Decimal("0")
    if txn.application is not None:
        expected = Decimal(str(txn.application.amount_requested or 0))
    settled = sum(
        (Decimal(str(row.amount or 0)) for row in (txn.application.disbursements if txn.application else [])),
        Decimal("0"),
    )
    return expected, settled


def _status_for(expected: Decimal, settled: Decimal, txn_status: str) -> str:
    if settled == 0:
        if txn_status == TransactionStatus.COMPLETED:
            return "outstanding"
        return "outstanding"
    if abs(expected - settled) <= TWOPLACES:
        return "matched"
    return "mismatch"


def scan_reconciliation(db: Session, *, institution_id: str | None = None) -> list[ReconciliationItem]:
    query = (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.application))
        .order_by(CommodityTransaction.created_at.desc())
    )
    if institution_id:
        query = query.filter(CommodityTransaction.institution_id == institution_id)
    created: list[ReconciliationItem] = []
    for txn in query.limit(2000).all():
        existing = db.query(ReconciliationItem).filter(ReconciliationItem.transaction_id == txn.id).first()
        expected, settled = _amounts(txn)
        status = _status_for(expected, settled, txn.status)
        if existing:
            if existing.status not in {"exception", "matched"} or existing.status == "matched":
                # Keep officer-marked exceptions; refresh auto-matched / outstanding.
                if existing.status != "exception":
                    existing.expected_amount = expected
                    existing.settled_amount = settled
                    existing.status = status
            continue
        item = ReconciliationItem(
            institution_id=txn.institution_id,
            transaction_id=txn.id,
            application_id=txn.application_id,
            expected_amount=expected,
            settled_amount=settled,
            currency=(txn.application.currency if txn.application else "KES") or "KES",
            status=status,
        )
        db.add(item)
        created.append(item)
    db.flush()
    return created


def list_items(
    db: Session,
    *,
    institution_id: str | None = None,
    status: str | None = None,
    limit: int = 300,
) -> list[ReconciliationItem]:
    query = db.query(ReconciliationItem).order_by(ReconciliationItem.created_at.desc())
    if institution_id:
        query = query.filter(ReconciliationItem.institution_id == institution_id)
    if status:
        query = query.filter(ReconciliationItem.status == status)
    return query.limit(limit).all()


def resolve_item(
    db: Session,
    item: ReconciliationItem,
    *,
    status: str,
    note: str | None,
    actor_id: str | None,
) -> ReconciliationItem:
    if status not in {"matched", "exception", "outstanding"}:
        raise ValueError("status must be matched, exception, or outstanding")
    item.status = status
    item.note = (note or "").strip() or item.note
    item.resolved_by_id = actor_id
    db.flush()
    log_audit(
        db,
        entity_type="reconciliation_item",
        entity_id=item.id,
        actor=AuditActor.HUMAN,
        action="reconciliation.resolved",
        details=f"status={status}, note={item.note or ''}",
    )
    db.flush()
    return item


def item_to_dict(item: ReconciliationItem, institution_name: str | None = None) -> dict[str, Any]:
    return {
        "id": item.id,
        "institution_id": item.institution_id,
        "institution_name": institution_name,
        "transaction_id": item.transaction_id,
        "application_id": item.application_id,
        "expected_amount": str(item.expected_amount),
        "settled_amount": str(item.settled_amount),
        "currency": item.currency,
        "status": item.status,
        "note": item.note,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
