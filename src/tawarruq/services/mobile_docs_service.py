"""Branded HTML documents for Buruuj Lend mobile download/share."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, joinedload

from tawarruq.enums import InstallmentStatus
from tawarruq.models.application import FinancingApplication
from tawarruq.models.kenya_flow import AssetBatch, MurabahaContract, RepaymentInstallment
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.document_brand import (
    kv_sections,
    render_branded_document,
    section_table_block,
)
from tawarruq.services.trade_evidence_service import (
    TRADE_DOC_KINDS,
    build_trade_document,
    render_trade_document_html,
    trade_documents_payload,
)


def _resolve_batch(
    db: Session, application_id: str
) -> tuple[CommodityTransaction | None, AssetBatch | None]:
    txn = (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.legs))
        .filter(CommodityTransaction.application_id == application_id)
        .order_by(CommodityTransaction.created_at.desc())
        .first()
    )
    if not txn:
        return None, None
    for leg in txn.legs or []:
        batch = db.query(AssetBatch).filter(AssetBatch.leg_id == leg.id).first()
        if batch:
            return txn, batch
    return txn, None


def list_mobile_documents(
    db: Session, application: FinancingApplication
) -> list[dict[str, Any]]:
    _txn, batch = _resolve_batch(db, application.id)
    payload = trade_documents_payload(batch)
    contract = (
        db.query(MurabahaContract)
        .filter(MurabahaContract.application_id == application.id)
        .first()
    )
    has_installments = False
    if contract:
        has_installments = (
            db.query(RepaymentInstallment)
            .filter(RepaymentInstallment.contract_id == contract.id)
            .count()
            > 0
        )

    return [
        {
            "kind": "purchase_order",
            "label": "Purchase order (e-PO)",
            "group": "Trade evidence",
            "available": bool(payload and payload.get("purchase_order")),
            "filename": f"{(payload or {}).get('purchase_order') or 'epo'}.html",
        },
        {
            "kind": "supplier_invoice",
            "label": "Supplier invoice",
            "group": "Trade evidence",
            "available": bool(payload and payload.get("supplier_invoice")),
            "filename": f"{(payload or {}).get('supplier_invoice') or 'invoice'}.html",
        },
        {
            "kind": "delivery_order",
            "label": "Delivery order",
            "group": "Trade evidence",
            "available": bool(payload and payload.get("delivery_order")),
            "filename": f"{(payload or {}).get('delivery_order') or 'do'}.html",
        },
        {
            "kind": "statement",
            "label": "Repayment statement",
            "group": "Facility",
            "available": True,
            "filename": f"statement-{application.id[:8]}.html",
        },
        {
            "kind": "murabaha",
            "label": "Murabaha contract summary",
            "group": "Facility",
            "available": contract is not None,
            "filename": f"murabaha-{application.id[:8]}.html",
        },
        {
            "kind": "wad",
            "label": "Wa'd (purchase undertaking)",
            "group": "Facility",
            "available": bool(application.wad_accepted_at or application.wad_text),
            "filename": f"wad-{application.id[:8]}.html",
        },
        {
            "kind": "schedule",
            "label": "Installment schedule",
            "group": "Facility",
            "available": has_installments,
            "filename": f"schedule-{application.id[:8]}.html",
        },
    ]


def render_mobile_document_html(
    db: Session, application: FinancingApplication, kind: str
) -> tuple[str, str]:
    key = (kind or "").strip().lower().replace("-", "_")
    txn, batch = _resolve_batch(db, application.id)
    if key in TRADE_DOC_KINDS or key in {"do", "invoice", "epo"}:
        doc = build_trade_document(application, txn, batch, key)
        return render_trade_document_html(doc), str(doc.get("filename") or f"{key}.html")
    if key == "statement":
        return _render_statement(db, application)
    if key == "murabaha":
        return _render_murabaha(db, application)
    if key == "wad":
        return _render_wad(application)
    if key == "schedule":
        return _render_schedule(db, application)
    raise ValueError(f"Unknown document kind: {kind}")


def _party_rows(application: FinancingApplication) -> list[tuple[str, object | None]]:
    institution = application.institution.name if application.institution else "—"
    customer = (
        getattr(application.customer, "full_name", None)
        or application.customer_name
        or application.customer_ref
    )
    return [
        ("Customer", customer),
        ("Institution", institution),
        ("Platform", "Buruuj Fintech"),
        ("Facility id", application.id),
    ]


def _render_statement(
    db: Session, application: FinancingApplication
) -> tuple[str, str]:
    contract = (
        db.query(MurabahaContract)
        .filter(MurabahaContract.application_id == application.id)
        .first()
    )
    installments = []
    if contract:
        installments = (
            db.query(RepaymentInstallment)
            .filter(RepaymentInstallment.contract_id == contract.id)
            .order_by(RepaymentInstallment.installment_number)
            .all()
        )
    paid = sum(1 for i in installments if i.status == InstallmentStatus.PAID.value)
    outstanding = sum(
        (Decimal(str(i.amount)) for i in installments if i.status != InstallmentStatus.PAID.value),
        Decimal("0"),
    )

    if installments:
        schedule_html = section_table_block(
            "Installments",
            ["#", "Amount", "Status", "Due", "Paid", "Ref"],
            [
                [
                    i.installment_number,
                    f"KES {i.amount}",
                    i.status,
                    i.due_date.date() if i.due_date else "—",
                    i.paid_at.date() if i.paid_at else "—",
                    i.payment_ref or "—",
                ]
                for i in installments
            ],
        )
    else:
        schedule_html = kv_sections(
            [("Installments", [("Schedule", "No schedule issued yet")])]
        )

    html = render_branded_document(
        title="Repayment statement",
        subtitle="Official facility statement for Buruuj Lend",
        doc_ref=application.id[:8],
        eyebrow="Buruuj Lend · Facility statement",
        sections_html=kv_sections(
            [
                ("Parties", _party_rows(application)),
                (
                    "Summary",
                    [
                        ("Amount financed", f"KES {application.amount_requested}"),
                        ("Status", application.status),
                        ("Installments paid", f"{paid} of {len(installments)}"),
                        ("Outstanding", f"KES {outstanding}"),
                    ],
                ),
            ]
        )
        + schedule_html,
        filename_hint=application.id[:8],
    )
    return html, f"statement-{application.id[:8]}.html"


def _render_murabaha(
    db: Session, application: FinancingApplication
) -> tuple[str, str]:
    contract = (
        db.query(MurabahaContract)
        .filter(MurabahaContract.application_id == application.id)
        .first()
    )
    if not contract:
        raise ValueError("Murabaha contract is not available yet.")
    offer = application.offer
    html = render_branded_document(
        title="Murabaha contract summary",
        subtitle="Cost-plus sale terms (interest-free)",
        doc_ref=contract.id[:8],
        eyebrow="Buruuj Lend · Murabaha",
        sections_html=kv_sections(
            [
                ("Parties", _party_rows(application)),
                (
                    "Commercial terms",
                    [
                        ("Amount financed", f"KES {application.amount_requested}"),
                        ("Cost price", str(offer.cost_price) if offer else "—"),
                        ("Profit", str(offer.profit_amount) if offer else "—"),
                        ("Total payable", str(offer.total_payable) if offer else "—"),
                        ("Installments", contract.installment_count),
                    ],
                ),
                (
                    "Execution",
                    [
                        ("Contract id", contract.id),
                        ("Document hash", contract.document_hash),
                        ("Signature ref", contract.signature_ref),
                        ("Signed at", contract.signed_at.isoformat() if contract.signed_at else "—"),
                    ],
                ),
            ]
        ),
        filename_hint=contract.id[:8],
    )
    return html, f"murabaha-{application.id[:8]}.html"


def _render_wad(application: FinancingApplication) -> tuple[str, str]:
    if not (application.wad_accepted_at or application.wad_text):
        raise ValueError("Wa'd undertaking is not recorded yet.")
    text = application.wad_text or ""
    html = render_branded_document(
        title="Wa'd — purchase undertaking",
        subtitle="Customer undertaking before commodity acquisition",
        doc_ref=application.id[:8],
        eyebrow="Buruuj Lend · Wa'd",
        sections_html=kv_sections(
            [
                ("Parties", _party_rows(application)),
                (
                    "Undertaking",
                    [
                        (
                            "Accepted at",
                            application.wad_accepted_at.isoformat()
                            if application.wad_accepted_at
                            else "—",
                        ),
                        ("Wa'd text", text),
                    ],
                ),
            ]
        ),
        filename_hint=application.id[:8],
    )
    return html, f"wad-{application.id[:8]}.html"


def _render_schedule(
    db: Session, application: FinancingApplication
) -> tuple[str, str]:
    contract = (
        db.query(MurabahaContract)
        .filter(MurabahaContract.application_id == application.id)
        .first()
    )
    if not contract:
        raise ValueError("Installment schedule is not available yet.")
    installments = (
        db.query(RepaymentInstallment)
        .filter(RepaymentInstallment.contract_id == contract.id)
        .order_by(RepaymentInstallment.installment_number)
        .all()
    )
    if not installments:
        raise ValueError("Installment schedule is not available yet.")

    html = render_branded_document(
        title="Installment schedule",
        subtitle="Deferred Murabaha repayment plan",
        doc_ref=application.id[:8],
        eyebrow="Buruuj Lend · Schedule",
        sections_html=kv_sections([("Parties", _party_rows(application))])
        + section_table_block(
            "Schedule",
            ["#", "Amount", "Status", "Due", "Ref"],
            [
                [
                    i.installment_number,
                    f"KES {i.amount}",
                    i.status,
                    i.due_date.date() if i.due_date else "—",
                    i.payment_ref or "—",
                ]
                for i in installments
            ],
        ),
        filename_hint=application.id[:8],
    )
    return html, f"schedule-{application.id[:8]}.html"
