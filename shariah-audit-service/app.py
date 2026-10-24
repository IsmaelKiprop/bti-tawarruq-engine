"""
Standalone append-only Shariah audit microservice.

Run: SHARIAH_AUDIT_DATABASE_URL=sqlite:///./shariah_audit.db python shariah-audit-service/app.py
"""

from __future__ import annotations

import csv
import io
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("DATABASE_URL", os.environ.get("SHARIAH_AUDIT_DATABASE_URL", "sqlite:///./shariah_audit.db"))

from tawarruq.config import get_settings  # noqa: E402
from tawarruq.database import Base, SessionLocal, engine, get_db, init_db  # noqa: E402
from tawarruq.models.kenya_flow import ShariahAuditLog  # noqa: E402
from tawarruq.services.shariah_audit_service import export_shariah_ledger  # noqa: E402
from tawarruq.services.shariah_ledger_service import append_shariah_entry, verify_ledger_chain  # noqa: E402

get_settings.cache_clear()
init_db()

app = FastAPI(title="Buruuj Shariah Audit Service", version="1.0.0")

class ShariahEntryRequest(BaseModel):
    step_id: str
    entity_type: str
    entity_id: str
    actor_from: str
    actor_to: str
    payload: dict[str, Any] = Field(default_factory=dict)
    asset_ref_no: str | None = None
    details: str | None = None
    verified_at: datetime | None = None
    mno_receipt_id: str | None = None
    institution_id: str | None = None
    transaction_id: str | None = None
    application_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "shariah-audit"}


@app.post("/v1/entries", status_code=201)
def append_entry(payload: ShariahEntryRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    entry = append_shariah_entry(
        db,
        step_id=payload.step_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        actor_from=payload.actor_from,
        actor_to=payload.actor_to,
        payload=payload.payload,
        asset_ref_no=payload.asset_ref_no,
        details=payload.details,
        verified_at=payload.verified_at,
        mno_receipt_id=payload.mno_receipt_id,
        institution_id=payload.institution_id,
        transaction_id=payload.transaction_id,
        application_id=payload.application_id,
    )
    db.commit()
    return {"id": entry.id, "entry_hash": entry.entry_hash}


@app.get("/v1/verify-chain")
def verify_chain(
    institution_id: str | None = None,
    limit: int = Query(10_000, le=100_000),
    db: Session = Depends(get_db),
) -> dict:
    return verify_ledger_chain(db, institution_id=institution_id, limit=limit)


@app.get("/v1/export", response_model=None)
def export_ledger(
    format: str = Query("json", pattern="^(json|csv)$"),
    institution_id: str | None = None,
    application_id: str | None = None,
    limit: int = Query(10_000, le=100_000),
    db: Session = Depends(get_db),
) -> Response | list[dict]:
    rows = export_shariah_ledger(
        db,
        institution_id=institution_id,
        application_id=application_id,
        limit=limit,
    )
    if format == "csv":
        buffer = io.StringIO()
        if rows:
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shariah_audit_export.csv"},
        )
    return rows


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("SHARIAH_AUDIT_PORT", "8001"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False, app_dir=str(Path(__file__).parent))
