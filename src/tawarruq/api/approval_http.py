"""HTTP helper for maker-checker 202 responses."""

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from tawarruq.services.approval_service import maybe_queue


def queued_or_none(
    db: Session,
    request: Request,
    *,
    action: str,
    institution_id: str,
    amount=None,
    application_id: str | None = None,
    transaction_id: str | None = None,
    payload: dict | None = None,
    currency: str = "KES",
) -> JSONResponse | None:
    queued = maybe_queue(
        db,
        request,
        action=action,
        institution_id=institution_id,
        amount=amount,
        application_id=application_id,
        transaction_id=transaction_id,
        payload=payload,
        currency=currency,
    )
    if not queued:
        return None
    return JSONResponse(status_code=202, content=queued)
