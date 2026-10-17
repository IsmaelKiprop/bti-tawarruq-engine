from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tawarruq.enums import AuditActor
from tawarruq.models.audit import AuditEvent


def log_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    actor: AuditActor | str,
    action: str,
    details: str | None = None,
    evidence_ref: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        actor=str(actor),
        action=action,
        details=details,
        evidence_ref=evidence_ref,
        timestamp=datetime.now(UTC),
    )
    db.add(event)
    db.flush()
    return event
