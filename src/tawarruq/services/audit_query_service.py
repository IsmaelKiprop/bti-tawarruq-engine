import csv
import io
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tawarruq.models.audit import AuditEvent

_MIN_TS = datetime.min.replace(tzinfo=UTC)


def query_audit_events(
    db: Session,
    *,
    entity_id: str | None = None,
    entity_type: str | None = None,
    actor: str | None = None,
    actor_user_id: str | None = None,
    institution_id: str | None = None,
    action_group: str | None = None,
    group_id: str | None = None,
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
    if actor_user_id:
        query = query.filter(AuditEvent.actor_user_id == actor_user_id)
    if action_group:
        query = query.filter(AuditEvent.action_group == action_group)
    if group_id:
        query = query.filter(AuditEvent.group_id == group_id)
    if from_ts:
        query = query.filter(AuditEvent.timestamp >= from_ts)
    if to_ts:
        query = query.filter(AuditEvent.timestamp <= to_ts)
    if institution_id:
        # Prefer direct institution_id; also include legacy entity-scoped deal events.
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
        legacy_ids = set(app_ids + txn_ids)
        if legacy_ids:
            query = query.filter(
                (AuditEvent.institution_id == institution_id)
                | (AuditEvent.entity_id.in_(legacy_ids))
                | ((AuditEvent.entity_type == "institution") & (AuditEvent.entity_id == institution_id))
            )
        else:
            query = query.filter(
                (AuditEvent.institution_id == institution_id)
                | ((AuditEvent.entity_type == "institution") & (AuditEvent.entity_id == institution_id))
            )
    return query.order_by(AuditEvent.timestamp.desc()).offset(offset).limit(limit).all()


def group_audit_events(events: list[AuditEvent]) -> list[dict]:
    """Collapse flat events into request/session groups (newest first)."""
    buckets: dict[str, dict] = {}
    order: list[str] = []
    for event in events:
        key = event.group_id or event.id
        if key not in buckets:
            buckets[key] = {
                "group_id": event.group_id or event.id,
                "action_group": event.action_group or "ops",
                "institution_id": event.institution_id,
                "actor_user_id": event.actor_user_id,
                "actor": event.actor,
                "started_at": event.timestamp,
                "ended_at": event.timestamp,
                "events": [],
            }
            order.append(key)
        bucket = buckets[key]
        bucket["events"].append(event)
        if event.timestamp and (bucket["started_at"] is None or event.timestamp < bucket["started_at"]):
            bucket["started_at"] = event.timestamp
        if event.timestamp and (bucket["ended_at"] is None or event.timestamp > bucket["ended_at"]):
            bucket["ended_at"] = event.timestamp
        if not bucket["institution_id"] and event.institution_id:
            bucket["institution_id"] = event.institution_id
        if not bucket["actor_user_id"] and event.actor_user_id:
            bucket["actor_user_id"] = event.actor_user_id
        if event.action_group:
            bucket["action_group"] = event.action_group
    # Keep newest groups first; within each group show chronological events
    for key in order:
        buckets[key]["events"] = sorted(
            buckets[key]["events"],
            key=lambda e: e.timestamp or _MIN_TS,
        )
    order.sort(key=lambda k: buckets[k]["ended_at"] or _MIN_TS, reverse=True)
    return [buckets[k] for k in order]


def export_audit_csv(events: list[AuditEvent]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "group_id",
            "action_group",
            "institution_id",
            "actor_user_id",
            "entity_type",
            "entity_id",
            "actor",
            "action",
            "details",
            "evidence_ref",
            "http_method",
            "http_path",
            "http_status",
            "timestamp",
        ]
    )
    for event in events:
        writer.writerow(
            [
                event.id,
                event.group_id or "",
                event.action_group or "",
                event.institution_id or "",
                event.actor_user_id or "",
                event.entity_type,
                event.entity_id,
                event.actor,
                event.action,
                event.details or "",
                event.evidence_ref or "",
                event.http_method or "",
                event.http_path or "",
                event.http_status if event.http_status is not None else "",
                event.timestamp.isoformat() if event.timestamp else "",
            ]
        )
    return buffer.getvalue()
