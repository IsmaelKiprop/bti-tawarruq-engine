"""In-app inbox + optional SMS/push queue for mobile accounts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.models.mobile_account import MobileAccount
from tawarruq.models.mobile_notification import MobileNotification


def push_notification(
    db: Session,
    account: MobileAccount,
    *,
    kind: str,
    title: str,
    body: str,
    application_id: str | None = None,
    queue_sms: bool = True,
    queue_push: bool = True,
) -> MobileNotification:
    row = MobileNotification(
        account_id=account.id,
        kind=kind,
        title=title,
        body=body,
        application_id=application_id,
        read=False,
        sms_queued=False,
        push_queued=False,
    )
    db.add(row)
    db.flush()

    if queue_sms and account.phone:
        _write_sms_outbox(account.phone, title, body)
        row.sms_queued = True
    if queue_push:
        _write_push_outbox(account.id, title, body, getattr(account, "push_token", None))
        row.push_queued = True
    db.flush()
    return row


def list_notifications(db: Session, account_id: str, *, limit: int = 40) -> list[dict[str, Any]]:
    rows = (
        db.query(MobileNotification)
        .filter(MobileNotification.account_id == account_id)
        .order_by(MobileNotification.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_public(r) for r in rows]


def unread_count(db: Session, account_id: str) -> int:
    return (
        db.query(MobileNotification)
        .filter(MobileNotification.account_id == account_id, MobileNotification.read.is_(False))
        .count()
    )


def mark_read(db: Session, account_id: str, notification_id: str | None = None) -> int:
    q = db.query(MobileNotification).filter(
        MobileNotification.account_id == account_id,
        MobileNotification.read.is_(False),
    )
    if notification_id:
        q = q.filter(MobileNotification.id == notification_id)
    count = 0
    for row in q.all():
        row.read = True
        count += 1
    db.flush()
    return count


def notify_account_by_customer(
    db: Session,
    customer_id: str,
    *,
    kind: str,
    title: str,
    body: str,
    application_id: str | None = None,
) -> MobileNotification | None:
    account = (
        db.query(MobileAccount)
        .filter(MobileAccount.customer_id == customer_id, MobileAccount.active.is_(True))
        .first()
    )
    if not account:
        return None
    return push_notification(
        db,
        account,
        kind=kind,
        title=title,
        body=body,
        application_id=application_id,
    )


def _public(row: MobileNotification) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "title": row.title,
        "body": row.body,
        "application_id": row.application_id,
        "read": row.read,
        "sms_queued": row.sms_queued,
        "push_queued": row.push_queued,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _outbox_dir() -> Path:
    settings = get_settings()
    root = Path(getattr(settings, "customer_mail_path", None) or "data/mail")
    path = root / "outbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_sms_outbox(phone: str, title: str, body: str) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = _outbox_dir() / f"sms-{stamp}-{phone[-4:]}.txt"
    path.write_text(f"TO: {phone}\nSUBJECT: {title}\n\n{body}\n", encoding="utf-8")


def _write_push_outbox(account_id: str, title: str, body: str, push_token: str | None) -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = _outbox_dir() / f"push-{stamp}-{account_id[:8]}.txt"
    path.write_text(
        f"ACCOUNT: {account_id}\nTOKEN: {push_token or 'none'}\nTITLE: {title}\n\n{body}\n",
        encoding="utf-8",
    )
