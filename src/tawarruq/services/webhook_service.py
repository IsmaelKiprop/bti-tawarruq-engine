import hashlib
import hmac
import json
import logging
import secrets
from typing import Any

import httpx
from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.enums import WebhookEvent
from tawarruq.models.integration import WebhookSubscription

logger = logging.getLogger(__name__)


def create_webhook(
    db: Session,
    institution_id: str,
    url: str,
    events: list[str],
) -> tuple[WebhookSubscription, str]:
    secret = secrets.token_urlsafe(32)
    sub = WebhookSubscription(
        institution_id=institution_id,
        url=url,
        events=",".join(events),
        secret=secret,
    )
    db.add(sub)
    db.flush()
    return sub, secret


def list_webhooks(db: Session, institution_id: str | None = None) -> list[WebhookSubscription]:
    query = db.query(WebhookSubscription).filter(WebhookSubscription.active.is_(True))
    if institution_id:
        query = query.filter(WebhookSubscription.institution_id == institution_id)
    return query.order_by(WebhookSubscription.created_at.desc()).all()


def _sign_payload(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def dispatch_webhook_event(
    db: Session,
    institution_id: str,
    event: WebhookEvent | str,
    data: dict[str, Any],
) -> None:
    event_name = str(event)
    subs = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.institution_id == institution_id,
            WebhookSubscription.active.is_(True),
        )
        .all()
    )
    body = {"event": event_name, "data": data}
    payload = json.dumps(body, default=str).encode()
    for sub in subs:
        subscribed = [e.strip() for e in sub.events.split(",")]
        if event_name not in subscribed and "*" not in subscribed:
            continue
        deliver_signed_webhook(
            url=sub.url,
            secret=sub.secret,
            payload=payload,
            event_name=event_name,
        )


def deliver_signed_webhook(
    url: str,
    secret: str,
    payload: bytes,
    event_name: str,
) -> bool:
    settings = get_settings()
    signature = _sign_payload(secret, payload)
    headers = {
        "Content-Type": "application/json",
        "X-BTI-Event": event_name,
        "X-BTI-Signature": signature,
    }
    for attempt in range(settings.webhook_max_retries):
        try:
            with httpx.Client(timeout=settings.webhook_timeout_seconds) as client:
                response = client.post(url, content=payload, headers=headers)
                response.raise_for_status()
                return True
        except httpx.HTTPError as exc:
            logger.warning(
                "Webhook delivery failed (attempt %s/%s) url=%s event=%s: %s",
                attempt + 1,
                settings.webhook_max_retries,
                url,
                event_name,
                exc,
            )
    return False
