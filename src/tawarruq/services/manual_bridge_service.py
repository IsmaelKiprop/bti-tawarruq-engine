"""Malaysia BSAS manual-bridge helpers for ops inbox and certificate paste."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, joinedload

from tawarruq.bsas.context_builder import resolve_customer_name
from tawarruq.bsas.desk_packet import format_batch_desk_email
from tawarruq.bsas.manual_bridge import ManualBridgeBackend
from tawarruq.bsas.product_codes import bsas_product_code
from tawarruq.config import get_settings
from tawarruq.enums import LegStatus, TransactionMode, TransactionStatus
from tawarruq.models.application import FinancingApplication
from tawarruq.models.institution import Institution
from tawarruq.models.transaction import CommodityTransaction, TransactionLeg


LEG_LABELS = {
    "1": "Leg 1: Agent purchase (BSAS)",
    "2": "Leg 2: Ownership transfer (OTC)",
    "3": "Leg 3: Sale to BMIS (STB)",
}


def _request_path(external_ref: str) -> Path:
    return ManualBridgeBackend().requests_dir / f"{external_ref}.json"


def _email_path(external_ref: str) -> Path:
    return ManualBridgeBackend().requests_dir / f"{external_ref}.email.txt"


def _reply_path(external_ref: str) -> Path:
    return ManualBridgeBackend().replies_dir / f"{external_ref}.json"


def load_manual_request(external_ref: str) -> dict[str, Any] | None:
    path = _request_path(external_ref)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_manual_email(external_ref: str) -> str | None:
    path = _email_path(external_ref)
    if path.exists():
        return path.read_text(encoding="utf-8")
    request = load_manual_request(external_ref)
    if request and request.get("email_body"):
        return str(request["email_body"])
    return None


def write_manual_reply(
    external_ref: str,
    *,
    certificate_number: str,
    issuer: str = "Bursa Malaysia Islamic Services Sdn.Bhd.",
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Persist the pasted e-certificate so Amanah file-watch and ops stay in sync."""
    backend = ManualBridgeBackend()
    reply = {
        "external_ref": external_ref,
        "certificate_number": certificate_number,
        "issuer": issuer,
        "confirmed_at": datetime.now(UTC).isoformat(),
        "source": "ops_portal",
    }
    if metadata:
        reply.update({k: v for k, v in metadata.items() if v is not None})
    path = backend.replies_dir / f"{external_ref}.json"
    path.write_text(json.dumps(reply, indent=2), encoding="utf-8")
    return path


def store_ecert_pdf(
    *,
    external_ref: str | None,
    certificate_number: str,
    filename: str,
    content: bytes,
) -> dict[str, str]:
    """Save uploaded Bursa e-cert PDF under the manual-bridge inbox."""
    backend = ManualBridgeBackend()
    pdf_dir = backend.inbox_dir / "ecerts"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name or "ecert.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"
    stem = (external_ref or certificate_number or "ecert").replace("/", "-").replace("\\", "-")
    dest = pdf_dir / f"{stem}__{safe_name}"
    dest.write_bytes(content)
    return {"pdf_path": str(dest), "pdf_filename": safe_name}


def inbox_summary() -> dict[str, Any]:
    settings = get_settings()
    backend = ManualBridgeBackend()
    requests = sorted(backend.requests_dir.glob("*.json"))
    replies = {p.stem for p in backend.replies_dir.glob("*.json")}
    pending_files = [p.stem for p in requests if p.stem not in replies]
    return {
        "inbox_dir": str(settings.manual_bridge_path),
        "request_count": len(requests),
        "reply_count": len(replies),
        "unanswered_request_refs": pending_files,
    }


def list_pending_manual_items(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    """Transactions/legs waiting for ops to paste a BSAS e-certificate."""
    rows = (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.institution))
        .filter(CommodityTransaction.mode == TransactionMode.MANUAL_BRIDGE)
        .filter(
            CommodityTransaction.status.in_(
                [
                    TransactionStatus.AWAITING_MANUAL,
                    TransactionStatus.EXECUTING,
                    TransactionStatus.CREATED,
                ]
            )
        )
        .order_by(CommodityTransaction.created_at.desc())
        .limit(limit)
        .all()
    )

    items: list[dict[str, Any]] = []
    for txn in rows:
        application = (
            db.query(FinancingApplication)
            .options(joinedload(FinancingApplication.offer), joinedload(FinancingApplication.customer))
            .filter(FinancingApplication.id == txn.application_id)
            .first()
        )
        for leg in sorted(txn.legs, key=lambda l: l.leg_number):
            if leg.status != LegStatus.AWAITING_CONFIRMATION:
                continue
            request_payload = load_manual_request(leg.external_ref) if leg.external_ref else None
            email_body = load_manual_email(leg.external_ref) if leg.external_ref else None
            offer = application.offer if application else None
            items.append(
                {
                    "transaction_id": txn.id,
                    "application_id": txn.application_id,
                    "institution_id": txn.institution_id,
                    "institution_code": txn.institution.code if txn.institution else None,
                    "institution_name": txn.institution.name if txn.institution else None,
                    "customer_ref": application.customer_ref if application else None,
                    "customer_name": resolve_customer_name(application) if application else None,
                    "currency": application.currency if application else "KES",
                    "amount_requested": str(application.amount_requested) if application else None,
                    "bid_amount": str(offer.cost_price) if offer else None,
                    "profit_amount": str(offer.profit_amount) if offer else None,
                    "murabaha_total": str(offer.total_payable) if offer else None,
                    "commodity_code": txn.commodity_code,
                    "product_code": bsas_product_code(txn.commodity_code),
                    "purchase_type": "A",
                    "transaction_status": txn.status,
                    "leg_number": leg.leg_number,
                    "leg_label": LEG_LABELS.get(leg.leg_number, f"Leg {leg.leg_number}"),
                    "leg_status": leg.status,
                    "external_ref": leg.external_ref,
                    "request": request_payload,
                    "email_body": email_body,
                    "created_at": txn.created_at.isoformat() if txn.created_at else None,
                }
            )
    return items


def get_leg_bridge_detail(db: Session, transaction_id: str, leg_number: str) -> dict[str, Any] | None:
    txn = db.get(CommodityTransaction, transaction_id)
    if not txn or txn.mode != TransactionMode.MANUAL_BRIDGE:
        return None
    leg = next((l for l in txn.legs if l.leg_number == leg_number), None)
    if not leg:
        return None
    application = (
        db.query(FinancingApplication)
        .options(joinedload(FinancingApplication.offer), joinedload(FinancingApplication.customer))
        .filter(FinancingApplication.id == txn.application_id)
        .first()
    )
    request_payload = load_manual_request(leg.external_ref) if leg.external_ref else None
    email_body = load_manual_email(leg.external_ref) if leg.external_ref else None
    reply_exists = bool(leg.external_ref and _reply_path(leg.external_ref).exists())
    offer = application.offer if application else None
    return {
        "transaction_id": txn.id,
        "application_id": txn.application_id,
        "institution_id": txn.institution_id,
        "institution_code": txn.institution.code if txn.institution else None,
        "institution_name": txn.institution.name if txn.institution else None,
        "customer_ref": application.customer_ref if application else None,
        "customer_name": resolve_customer_name(application) if application else None,
        "currency": application.currency if application else "KES",
        "amount_requested": str(application.amount_requested) if application else None,
        "bid_amount": str(offer.cost_price) if offer else None,
        "profit_amount": str(offer.profit_amount) if offer else None,
        "murabaha_total": str(offer.total_payable) if offer else None,
        "commodity_code": txn.commodity_code,
        "product_code": bsas_product_code(txn.commodity_code),
        "purchase_type": "A",
        "transaction_status": txn.status,
        "leg_number": leg.leg_number,
        "leg_label": LEG_LABELS.get(leg.leg_number, f"Leg {leg.leg_number}"),
        "leg_status": leg.status,
        "external_ref": leg.external_ref,
        "request": request_payload,
        "email_body": email_body,
        "reply_on_disk": reply_exists,
        "ops_instructions": [
            "Copy the Bursa desk email (or JSON packet) and send it to BSAS Ops / the commodity desk.",
            "Execute Leg 1 as Agent (A) using product code, bid, profit, and murabaha totals.",
            "For Leg 1 packets: proceed with OTC (Leg 2) and STB (Leg 3) immediately after purchase.",
            "Copy the e-certificate number from BSAS.",
            "Paste the certificate into the ops portal Confirm form (or POST /legs/{n}/confirm).",
            "Advance the next pending leg after confirmation.",
        ],
    }


def build_desk_batch(
    db: Session,
    *,
    institution_id: str | None = None,
    leg_number: str = "1",
) -> dict[str, Any]:
    """Aggregate unanswered Leg-1 desk requests into one Bursa-style email."""
    items = list_pending_manual_items(db, limit=200)
    scoped = [
        item
        for item in items
        if item["leg_number"] == leg_number
        and (not institution_id or item.get("institution_id") == institution_id)
    ]
    if not scoped:
        institution_name = ""
        institution_code = ""
        if institution_id:
            inst = db.get(Institution, institution_id)
            if inst:
                institution_name = inst.name
                institution_code = inst.code
        email = format_batch_desk_email(
            institution_name=institution_name or "Institution",
            institution_code=institution_code,
            customers=[],
        )
        return {
            "institution_id": institution_id,
            "institution_name": institution_name or None,
            "institution_code": institution_code or None,
            "leg_number": leg_number,
            "customer_count": 0,
            "customers": [],
            "email_body": email,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # Prefer a single institution batch; if mixed, group under first institution and note others.
    primary = scoped[0]
    institution_name = primary.get("institution_name") or "Institution"
    institution_code = primary.get("institution_code") or ""
    same_institution = all(item.get("institution_id") == primary.get("institution_id") for item in scoped)
    customers = []
    for item in scoped:
        if same_institution or item.get("institution_id") == primary.get("institution_id"):
            customers.append(
                {
                    "end_customer_name": item.get("customer_name") or item.get("customer_ref"),
                    "customer_ref": item.get("customer_ref"),
                    "external_ref": item.get("external_ref"),
                    "transaction_id": item.get("transaction_id"),
                    "application_id": item.get("application_id"),
                    "currency": item.get("currency") or "KES",
                    "bid_amount": float(item.get("bid_amount") or 0),
                    "profit_amount": float(item.get("profit_amount") or 0),
                    "murabaha_total": float(item.get("murabaha_total") or 0),
                    "product_code": item.get("product_code") or bsas_product_code(item.get("commodity_code") or "PALM_OIL"),
                    "purchase_type": "A",
                }
            )

    email = format_batch_desk_email(
        institution_name=institution_name,
        institution_code=institution_code,
        customers=customers,
    )

    # Persist latest batch snapshot for ops audit trail
    backend = ManualBridgeBackend()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    batch_path = backend.requests_dir / f"BATCH-{institution_code or 'ALL'}-{stamp}.email.txt"
    batch_path.write_text(email, encoding="utf-8")
    batch_json = backend.requests_dir / f"BATCH-{institution_code or 'ALL'}-{stamp}.json"
    batch_json.write_text(
        json.dumps(
            {
                "institution_code": institution_code,
                "institution_name": institution_name,
                "customers": customers,
                "email_body": email,
                "generated_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "institution_id": primary.get("institution_id"),
        "institution_name": institution_name,
        "institution_code": institution_code,
        "leg_number": leg_number,
        "customer_count": len(customers),
        "customers": customers,
        "email_body": email,
        "batch_email_path": str(batch_path),
        "batch_json_path": str(batch_json),
        "generated_at": datetime.now(UTC).isoformat(),
    }
