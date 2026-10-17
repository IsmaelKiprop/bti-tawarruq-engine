"""Operational metrics for monitoring dashboards and Prometheus export."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tawarruq.config import Settings
from tawarruq.models.application import FinancingApplication
from tawarruq.models.audit import AuditEvent
from tawarruq.models.institution import Institution
from tawarruq.models.integration import ApiKey, WebhookSubscription
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.manual_bridge_service import list_pending_manual_items
from tawarruq.services.monitoring import get_http_metrics


def collect_ops_metrics(db: Session, settings: Settings, institution_id: str | None = None) -> dict:
    app_q = select(FinancingApplication)
    txn_q = select(CommodityTransaction)
    if institution_id:
        app_q = app_q.where(FinancingApplication.institution_id == institution_id)
        txn_q = txn_q.where(CommodityTransaction.institution_id == institution_id)

    applications = db.scalars(app_q).all()
    transactions = db.scalars(txn_q).all()

    app_by_status: dict[str, int] = {}
    for app in applications:
        app_by_status[app.status] = app_by_status.get(app.status, 0) + 1

    txn_by_status: dict[str, int] = {}
    for txn in transactions:
        txn_by_status[txn.status] = txn_by_status.get(txn.status, 0) + 1

    pending_bridge = list_pending_manual_items(db)
    if institution_id:
        app_ids = {app.id for app in applications}
        pending_bridge = [item for item in pending_bridge if item.get("application_id") in app_ids]

    institution_count = db.scalar(select(func.count()).select_from(Institution)) or 0
    webhook_q = select(func.count()).select_from(WebhookSubscription).where(WebhookSubscription.active.is_(True))
    api_key_q = select(func.count()).select_from(ApiKey).where(ApiKey.active.is_(True))
    if institution_id:
        webhook_q = webhook_q.where(WebhookSubscription.institution_id == institution_id)
        api_key_q = api_key_q.where(ApiKey.institution_id == institution_id)

    recent_audit = db.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.timestamp >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))
    )

    http = get_http_metrics()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scoped_institution_id": institution_id,
        "applications_total": len(applications),
        "applications_by_status": app_by_status,
        "transactions_total": len(transactions),
        "transactions_by_status": txn_by_status,
        "manual_bridge_pending": len(pending_bridge),
        "institutions_total": institution_count if not institution_id else 1,
        "active_webhooks": db.scalar(webhook_q) or 0,
        "active_api_keys": db.scalar(api_key_q) or 0,
        "audit_events_today": recent_audit or 0,
        "amanah_enabled": settings.amanah_enabled,
        "amanah_write_enabled": settings.amanah_write_enabled,
        "auth_enabled": settings.auth_enabled,
        "kenya_integration_mode": settings.kenya_integration_mode,
        "http_requests_total": http["requests_total"],
        "http_errors_total": http["errors_total"],
        "http_latency_ms_avg": http["latency_ms_avg"],
        "http_by_status": {str(k): v for k, v in http.get("by_status", {}).items()},
        "http_top_paths": http.get("top_paths", {}),
    }


def render_prometheus(metrics: dict) -> str:
    lines: list[str] = []

    def gauge(name: str, value: float | int, labels: dict[str, str] | None = None) -> None:
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            lines.append(f"{name}{{{label_str}}} {value}")
        else:
            lines.append(f"{name} {value}")

    gauge("tawarruq_up", 1)
    gauge("tawarruq_applications_total", metrics["applications_total"])
    for status, count in metrics["applications_by_status"].items():
        gauge("tawarruq_applications_by_status", count, {"status": status})
    gauge("tawarruq_transactions_total", metrics["transactions_total"])
    for status, count in metrics["transactions_by_status"].items():
        gauge("tawarruq_transactions_by_status", count, {"status": status})
    gauge("tawarruq_manual_bridge_pending", metrics["manual_bridge_pending"])
    gauge("tawarruq_institutions_total", metrics["institutions_total"])
    gauge("tawarruq_active_webhooks", metrics["active_webhooks"])
    gauge("tawarruq_active_api_keys", metrics["active_api_keys"])
    gauge("tawarruq_audit_events_today", metrics["audit_events_today"])
    gauge("tawarruq_http_requests_total", metrics["http_requests_total"])
    gauge("tawarruq_http_errors_total", metrics["http_errors_total"])
    gauge("tawarruq_http_latency_ms_avg", metrics["http_latency_ms_avg"])
    gauge("tawarruq_amanah_write_enabled", 1 if metrics["amanah_write_enabled"] else 0)
    gauge("tawarruq_auth_enabled", 1 if metrics["auth_enabled"] else 0)
    return "\n".join(lines) + "\n"
