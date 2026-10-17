import logging

import httpx

from tawarruq.config import get_settings

logger = logging.getLogger(__name__)


def escalate(message: str, *, entity_id: str, evidence_ref: str | None = None) -> None:
    """Send escalation to configured webhook (Slack/WhatsApp bridge)."""
    settings = get_settings()
    payload = {
        "source": "amanah",
        "message": message,
        "entity_id": entity_id,
        "evidence_ref": evidence_ref,
    }
    logger.warning("AMANAH ESCALATION: %s | entity=%s", message, entity_id)

    if not settings.amanah_escalation_webhook_url:
        return

    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(settings.amanah_escalation_webhook_url, json=payload)
    except httpx.HTTPError as exc:
        logger.error("Failed to send escalation webhook: %s", exc)
