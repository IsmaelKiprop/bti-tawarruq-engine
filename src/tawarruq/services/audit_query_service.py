import csv
import io
from datetime import datetime

from sqlalchemy.orm import Session

from tawarruq.models.audit import AuditEvent


def query_audit_events(
    db: Session,
    *,
    entity_id: str | None = None,
    entity_type: str | None = None,
    actor: str | None = None,
    institution_id: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[AuditEvent]:
    query = db.query(AuditEvent)
    if entity_id:
        query = query.filter(AuditEvent.entity_id == entity_id)
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if actor:
        query = query.filter(AuditEvent.actor == actor)
    if from_ts:
        query = query.filter(AuditEvent.timestamp >= from_ts)
    if to_ts:
        query = query.filter(AuditEvent.timestamp <= to_ts)
    if institution_id:
        from tawarruq.models.application import FinancingApplication
        from tawarruq.models.transaction import CommodityTransaction

        app_ids = [
            row[0]
            for row in db.query(FinancingApplication.id)
            .filter(FinancingApplication.institution_id == institution_id)
            .all()
        ]
        txn_ids = [
            row[0]
            for row in db.query(CommodityTransaction.id)
            .filter(CommodityTransaction.institution_id == institution_id)
            .all()
        ]
        allowed = set(app_ids + txn_ids)
        if allowed:
            query = query.filter(AuditEvent.entity_id.in_(allowed))
        else:
            return []
    return query.order_by(AuditEvent.timestamp.asc()).offset(offset).limit(limit).all()


def export_audit_csv(events: list[AuditEvent]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "entity_type", "entity_id", "actor", "action", "details", "evidence_ref", "timestamp"])
    for event in events:
        writer.writerow(
            [
                event.id,
                event.entity_type,
                event.entity_id,
                event.actor,
                event.action,
                event.details or "",
                event.evidence_ref or "",
                event.timestamp.isoformat() if event.timestamp else "",
            ]
        )
    return buffer.getvalue()
