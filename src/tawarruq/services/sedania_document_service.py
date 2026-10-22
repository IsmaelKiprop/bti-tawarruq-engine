"""AS SIDQ trade pack for Sedania financing: PO, invoice, DO, e-Cert, muqassah, CASA, delivery."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tawarruq.enums import VaultCertificateKind
from tawarruq.models.execution import TawarruqExecution
from tawarruq.services.document_brand import kv_sections, render_branded_document
from tawarruq.services.legal_token_service import AS_SIDQ_PLATFORM, COMMODITY_LABEL, SASC_LEGAL_NAME

TRADE_DOC_LABELS = {
    VaultCertificateKind.PURCHASE_ORDER: "Purchase Order",
    VaultCertificateKind.COMMODITY_INVOICE: "Commodity Invoice",
    VaultCertificateKind.DELIVERY_ORDER: "Delivery Order",
    VaultCertificateKind.TRADING_ECERT: "Trading e-Cert",
    VaultCertificateKind.MUQASSAH: "Muqassah set-off instruction",
    VaultCertificateKind.CASA_ADVICE: "CASA credit advice",
    VaultCertificateKind.PHYSICAL_DELIVERY: "Physical delivery notice",
    VaultCertificateKind.CMP: "Commodity Murabahah Program",
}

DOC_KIND_ALIASES = {
    "po": VaultCertificateKind.PURCHASE_ORDER,
    "e-po": VaultCertificateKind.PURCHASE_ORDER,
    "purchase_order": VaultCertificateKind.PURCHASE_ORDER,
    "invoice": VaultCertificateKind.COMMODITY_INVOICE,
    "commodity_invoice": VaultCertificateKind.COMMODITY_INVOICE,
    "do": VaultCertificateKind.DELIVERY_ORDER,
    "delivery_order": VaultCertificateKind.DELIVERY_ORDER,
    "ecert": VaultCertificateKind.TRADING_ECERT,
    "e-cert": VaultCertificateKind.TRADING_ECERT,
    "trading_ecert": VaultCertificateKind.TRADING_ECERT,
    "muqassah": VaultCertificateKind.MUQASSAH,
    "casa": VaultCertificateKind.CASA_ADVICE,
    "casa_advice": VaultCertificateKind.CASA_ADVICE,
    "physical": VaultCertificateKind.PHYSICAL_DELIVERY,
    "physical_delivery": VaultCertificateKind.PHYSICAL_DELIVERY,
    "cmp": VaultCertificateKind.CMP,
}


def normalize_sedania_doc_kind(kind: str) -> str:
    key = (kind or "").strip().lower().replace("-", "_")
    resolved = DOC_KIND_ALIASES.get(key, key)
    allowed = {item.value for item in TRADE_DOC_LABELS}
    allowed.update({VaultCertificateKind.CMP})
    if resolved not in allowed and resolved not in {k.value for k in VaultCertificateKind}:
        raise ValueError("Unknown Sedania document kind.")
    return str(resolved)


def trade_pack_refs(token: str) -> dict[str, str]:
    slug = token[:8].upper()
    return {
        "purchase_order": f"PO-ASSIDQ-{slug}",
        "commodity_invoice": f"INV-AIRTIME-{slug}",
        "delivery_order": f"DO-AIRTIME-{slug}",
        "trading_ecert": f"ECERT-ASSIDQ-{slug}",
        "muqassah": f"MUQ-{slug}",
        "casa": f"CASA-CR-{slug}",
        "physical": f"PD-HAKIKI-{slug}",
    }


def _money(amount: object, currency: str) -> str:
    return f"{currency} {amount}"


def render_sedania_document(execution: TawarruqExecution, kind: str, payload: dict[str, Any]) -> str:
    resolved = normalize_sedania_doc_kind(kind)
    title = TRADE_DOC_LABELS.get(resolved, payload.get("title") or resolved.replace("_", " ").title())
    doc_ref = (
        payload.get("ref")
        or payload.get("certificate_number")
        or {
            VaultCertificateKind.PURCHASE_ORDER: execution.purchase_order_ref,
            VaultCertificateKind.COMMODITY_INVOICE: execution.commodity_invoice_ref,
            VaultCertificateKind.DELIVERY_ORDER: execution.delivery_order_ref,
            VaultCertificateKind.TRADING_ECERT: execution.trading_ecert_ref,
            VaultCertificateKind.MUQASSAH: execution.muqassah_ref,
            VaultCertificateKind.CASA_ADVICE: execution.casa_ref,
        }.get(resolved)
    )
    issued = payload.get("issued_at") or (
        execution.created_at.isoformat() if execution.created_at else datetime.now(UTC).isoformat()
    )
    institution = payload.get("institution_name") or (
        execution.institution.name if execution.institution else "Institution"
    )
    customer = payload.get("customer_name") or (
        execution.customer.full_name if execution.customer else execution.customer_id
    )
    currency = execution.currency
    amount = payload.get("amount") or execution.amount
    sections = kv_sections(
        [
            (
                "Document",
                [
                    ("Type", title),
                    ("Number", doc_ref),
                    ("Issued", str(issued)[:19]),
                    ("Platform", AS_SIDQ_PLATFORM),
                ],
            ),
            (
                "Parties",
                [
                    ("Financier", institution),
                    ("Customer", customer),
                    ("Supplier", execution.supplier_ref or "Telecommunication Airtime Aggregator"),
                    ("Independent agent / messenger", SASC_LEGAL_NAME),
                    ("Purchaser", execution.purchaser_ref),
                ],
            ),
            (
                "Commodity",
                [
                    ("Commodity", COMMODITY_LABEL),
                    ("Spot amount", _money(amount, currency)),
                    ("Deferred Murabahah", _money(execution.deferred_price, currency)),
                    ("Batch", execution.sedania_batch_id),
                    ("Possession", payload.get("possession") or "qabd hukmi"),
                ],
            ),
            (
                "Evidence refs",
                [
                    ("Purchase Order", execution.purchase_order_ref),
                    ("Commodity Invoice", execution.commodity_invoice_ref),
                    ("Delivery Order", execution.delivery_order_ref),
                    ("Trading e-Cert", execution.trading_ecert_ref),
                    ("Muqassah", execution.muqassah_ref),
                    ("CASA credit", execution.casa_ref),
                ],
            ),
        ]
    )
    notes = {
        VaultCertificateKind.PURCHASE_ORDER: (
            "The institution orders telecommunication airtime from the supplier on a spot and credit basis via AS SIDQ."
        ),
        VaultCertificateKind.COMMODITY_INVOICE: (
            "The supplier bills the institution for the same lot. Murabahah cost must match this invoice."
        ),
        VaultCertificateKind.DELIVERY_ORDER: (
            "The supplier releases the lot so the institution obtains constructive possession (qabd hukmi) before any sale to the customer."
        ),
        VaultCertificateKind.TRADING_ECERT: (
            "AS SIDQ trading e-certificate covering purchase, qabd hukmi, and the deferred Murabahah sale to the customer."
        ),
        VaultCertificateKind.MUQASSAH: (
            "The commodity purchaser authorizes the bank to pay the customer on its behalf. "
            "The purchaser then agrees to pay the commodity seller for set-off (muqassah)."
        ),
        VaultCertificateKind.CASA_ADVICE: (
            "The bank credits the customer's Current or Savings Account after the independent sale and, on the approved flow, after muqassah."
        ),
        VaultCertificateKind.PHYSICAL_DELIVERY: (
            "The customer opted to keep the commodity. SEDANIA As Salam Capital arranges physical delivery (qabd hakiki) with the supplier after the deferred price is fully settled."
        ),
        VaultCertificateKind.CMP: (
            "Financing contract and entry into the Commodity Murabahah Program. Agency of SASC is optional under the T&C."
        ),
    }
    return render_branded_document(
        title=str(title),
        subtitle="Sedania As-Sidq financing evidence",
        doc_ref=str(doc_ref or "—"),
        eyebrow="Buruuj Lend · AS SIDQ trade pack",
        sections_html=sections,
        note=notes.get(resolved, "Official Sedania financing evidence."),
        filename_hint=str(doc_ref or resolved),
    )
