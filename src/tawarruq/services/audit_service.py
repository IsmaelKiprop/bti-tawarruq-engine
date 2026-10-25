from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tawarruq.enums import AuditActor
from tawarruq.models.audit import AuditEvent


def classify_action_group(path: str | None = None, action: str | None = None) -> str:
    """Bucket audit actions for grouped ops views."""
    hay = f"{path or ''} {action or ''}".lower()
    if "audit/ui" in hay or hay.startswith("ui.") or " ui." in hay:
        return "ui"
    if any(token in hay for token in ("/ops/auth", "auth.", "login", "mfa", "password")):
        return "auth"
    if any(token in hay for token in ("/ops/auth/users", "ops_user", "/users")):
        return "users"
    if "institution" in hay:
        return "institutions"
    if "integration" in hay or "webhook" in hay or "api-key" in hay:
        return "integrations"
    if "/kenya" in hay or "kenya" in hay:
        return "kenya"
    if "sedania" in hay:
        return "sedania"
    if "malaysia" in hay or "manual-bridge" in hay or "bsas" in hay:
        return "malaysia"
    if "approval" in hay:
        return "approvals"
    if "billing" in hay or "reconcil" in hay:
        return "finance"
    if "shariah" in hay:
        return "shariah"
    if "application" in hay or "transaction" in hay or "customer" in hay:
        return "deals"
    return "ops"


def log_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    actor: AuditActor | str,
    action: str,
    details: str | None = None,
    evidence_ref: str | None = None,
    institution_id: str | None = None,
    actor_user_id: str | None = None,
    group_id: str | None = None,
    action_group: str | None = None,
    http_method: str | None = None,
    http_path: str | None = None,
    http_status: int | None = None,
) -> AuditEvent:
    event = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        actor=str(actor),
        action=action,
        details=details,
        evidence_ref=evidence_ref,
        timestamp=datetime.now(UTC),
        institution_id=institution_id,
        actor_user_id=actor_user_id,
        group_id=group_id,
        action_group=action_group or classify_action_group(http_path, action),
        http_method=http_method,
        http_path=http_path,
        http_status=http_status,
    )
    db.add(event)
    db.flush()
    return event
