"""Wa'd (undertaking to purchase) and Kenya trade evidence (e-PO, invoice, DO)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from tawarruq.enums import ShariahStepId
from tawarruq.models.application import FinancingApplication
from tawarruq.models.kenya_flow import AssetBatch
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.shariah_audit_service import log_shariah_step


@lru_cache(maxsize=1)
def _buruuj_logo_data_uri() -> str:
    roots = Path(__file__).resolve().parents
    candidates = [
        roots[3] / "portal" / "public" / "brand" / "buruuj-logo.png",
        roots[3] / "assets" / "brand" / "buruuj-logo.png",
        roots[3] / "mobile" / "assets" / "buruuj-logo.png",
        roots[3] / "portal" / "public" / "brand" / "buruuj-logo.jpg",
        roots[3] / "assets" / "brand" / "buruuj-logo.jpg",
    ]
    for path in candidates:
        if path.is_file():
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            return f"data:{mime};base64,{encoded}"
    return ""


TRADE_DOC_KINDS = {
    "purchase_order": {
        "title": "Electronic Purchase Order",
        "short": "e-PO",
        "field": "purchase_order",
    },
    "supplier_invoice": {
        "title": "Supplier Invoice",
        "short": "Invoice",
        "field": "supplier_invoice",
    },
    "delivery_order": {
        "title": "Delivery Order",
        "short": "DO",
        "field": "delivery_order",
    },
}

_KIND_ALIASES = {
    "epo": "purchase_order",
    "e-po": "purchase_order",
    "invoice": "supplier_invoice",
    "do": "delivery_order",
}

DEFAULT_WAD_TEXT = (
    "I undertake to purchase the commodity once the institution has acquired constructive possession, "
    "at the Murabaha cost-plus price to be disclosed. After ownership transfers to me, Buruuj Fintech "
    "may be appointed as my wakeel to sell the commodity to an independent buyer."
)


def record_purchase_undertaking(
    db: Session,
    application: FinancingApplication,
    *,
    text: str | None = None,
) -> FinancingApplication:
    if application.wad_accepted_at:
        return application
    application.wad_text = (text or DEFAULT_WAD_TEXT).strip()
    application.wad_accepted_at = datetime.now(UTC)
    institution_name = application.institution.name if application.institution else "institution"
    customer_name = application.customer_name or application.customer_ref
    log_shariah_step(
        db,
        step_id=ShariahStepId.WAD_UNDERTAKING,
        entity_type="financing_application",
        entity_id=application.id,
        actor_from=customer_name,
        actor_to=institution_name,
        payload={
            "application_id": application.id,
            "wad_text": application.wad_text,
        },
        asset_ref_no=application.customer_ref,
        institution_id=application.institution_id,
        application_id=application.id,
    )
    db.flush()
    return application


def classify_kenya_commodity(code: str | None) -> dict[str, str]:
    raw = (code or "").upper()
    kind = "float" if ("FLOAT" in raw or "DEALER" in raw) else "airtime"
    if "AIRTEL" in raw:
        operator = "Airtel"
        op_slug = "AIRTEL"
    elif "DEALER" in raw:
        operator = "Agent Dealer"
        op_slug = "DEALER"
    else:
        operator = "Safaricom"
        op_slug = "SAFARICOM"
    slug = f"{kind.upper()}-{op_slug}"
    return {
        "kind": kind,
        "operator": operator,
        "slug": slug,
        "label": f"{operator} {kind}",
        "code": raw or "UNKNOWN",
    }


def issue_trade_documents(
    batch: AssetBatch,
    *,
    source_dealer_code: str | None = None,
    commodity_code: str | None = None,
) -> AssetBatch:
    token = (batch.batch_id or batch.id or "LOT").replace(" ", "")[-12:].upper()
    classified = classify_kenya_commodity(commodity_code or batch.mno_code)
    if not batch.purchase_order_ref:
        batch.purchase_order_ref = f"EPO-{classified['slug']}-{token}"
    if not batch.supplier_invoice_ref:
        batch.supplier_invoice_ref = f"INV-{classified['slug']}-{token}"
    do_prefix = f"DO-{classified['slug']}-"
    current_do = batch.delivery_order_ref or ""
    if not current_do.startswith(do_prefix):
        batch.delivery_order_ref = f"{do_prefix}{token}"
    if source_dealer_code:
        batch.source_dealer_code = source_dealer_code
    return batch


def trade_documents_payload(batch: AssetBatch | None) -> dict | None:
    if not batch or not batch.purchase_order_ref:
        return None
    classified = classify_kenya_commodity(batch.mno_code)
    return {
        "purchase_order": batch.purchase_order_ref,
        "supplier_invoice": batch.supplier_invoice_ref,
        "delivery_order": batch.delivery_order_ref,
        "batch_id": batch.batch_id,
        "receipt_id": batch.mno_receipt_id,
        "source_dealer": batch.source_dealer_code,
        "commodity_kind": classified["kind"],
        "commodity_operator": classified["operator"],
        "commodity_label": classified["label"],
        "downloadable": True,
    }


def normalize_trade_doc_kind(kind: str) -> str:
    key = (kind or "").strip().lower().replace("-", "_")
    resolved = _KIND_ALIASES.get(key, key)
    if resolved not in TRADE_DOC_KINDS:
        raise ValueError("Use purchase_order, supplier_invoice, or delivery_order.")
    return resolved


def build_trade_document(
    application: FinancingApplication,
    transaction: CommodityTransaction | None,
    batch: AssetBatch | None,
    kind: str,
) -> dict[str, Any]:
    docs = trade_documents_payload(batch)
    if not docs:
        raise ValueError("Trade documents are not issued yet.")
    resolved = normalize_trade_doc_kind(kind)
    meta = TRADE_DOC_KINDS[resolved]
    number = docs.get(meta["field"])
    if not number:
        raise ValueError(f"{meta['title']} is not issued yet.")
    institution = application.institution.name if application.institution else "Institution"
    customer = getattr(application.customer, "full_name", None) or application.customer_name or application.customer_ref
    issued = None
    if transaction and transaction.created_at:
        issued = transaction.created_at.isoformat()
    elif application.created_at:
        issued = application.created_at.isoformat()
    return {
        "kind": resolved,
        "title": meta["title"],
        "short": meta["short"],
        "number": number,
        "customer_ref": application.customer_ref,
        "customer_name": customer,
        "institution_name": institution,
        "commodity": docs.get("commodity_label") or (transaction.commodity_code if transaction else None),
        "commodity_kind": docs.get("commodity_kind"),
        "commodity_operator": docs.get("commodity_operator"),
        "commodity_label": docs.get("commodity_label"),
        "amount": str(application.amount_requested),
        "currency": application.currency or "KES",
        "batch_id": docs.get("batch_id"),
        "receipt_id": docs.get("receipt_id"),
        "source_dealer": docs.get("source_dealer"),
        "purchase_order": docs.get("purchase_order"),
        "supplier_invoice": docs.get("supplier_invoice"),
        "delivery_order": docs.get("delivery_order"),
        "issued_at": issued,
        "downloadable": True,
        "filename": f"{number}.html",
    }


def render_trade_document_html(doc: dict[str, Any]) -> str:
    from tawarruq.services.document_brand import kv_sections, render_branded_document

    purpose = {
        "purchase_order": "The institution orders the commodity from the supplier. This is the buy ticket for Leg 1.",
        "supplier_invoice": "The supplier bills the institution for the same lot. Cost on the later Murabaha must match this invoice.",
        "delivery_order": "The supplier releases the lot so constructive possession can be sealed before any sale to the customer.",
    }[doc["kind"]]
    issued = doc.get("issued_at") or ""
    issued_label = issued[:10] if issued else "Not recorded"
    sections = kv_sections(
        [
            (
                "Document",
                [
                    ("Type", doc["title"]),
                    ("Number", doc["number"]),
                    ("Issued", issued_label),
                ],
            ),
            (
                "Parties",
                [
                    ("Institution", doc.get("institution_name")),
                    ("Customer", doc.get("customer_name")),
                    ("Platform", "Buruuj Fintech"),
                    ("Application", doc.get("customer_ref")),
                ],
            ),
            (
                "Commodity",
                [
                    ("Commodity", doc.get("commodity_label") or doc.get("commodity")),
                    ("Kind", doc.get("commodity_kind")),
                    ("Operator", doc.get("commodity_operator")),
                    ("Amount", f"{doc.get('currency')} {doc.get('amount')}"),
                    ("Source dealer", doc.get("source_dealer")),
                ],
            ),
            (
                "Evidence refs",
                [
                    ("e-PO", doc.get("purchase_order")),
                    ("Invoice", doc.get("supplier_invoice")),
                    ("Delivery order", doc.get("delivery_order")),
                    ("Batch", doc.get("batch_id")),
                    ("Receipt", doc.get("receipt_id")),
                ],
            ),
        ]
    )
    return render_branded_document(
        title=str(doc["title"]),
        subtitle="Kenya trade evidence for Shariah audit",
        doc_ref=str(doc["number"]),
        eyebrow="Buruuj Lend · Trade evidence",
        sections_html=sections,
        note=purpose + " Buruuj Fintech operates the technology rail; the named institution is the financier.",
        filename_hint=str(doc["number"]),
    )
