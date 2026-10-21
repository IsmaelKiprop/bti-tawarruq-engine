"""Platform usage fees and invoices for BTI Finance."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from tawarruq.enums import AuditActor
from tawarruq.models.application import FinancingApplication
from tawarruq.models.controls import BillingInvoice
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.institution import Institution
from tawarruq.services.audit_service import log_audit

TWOPLACES = Decimal("0.01")


def list_invoices(db: Session, *, institution_id: str | None = None, limit: int = 200) -> list[BillingInvoice]:
    query = db.query(BillingInvoice).order_by(BillingInvoice.issued_at.desc())
    if institution_id:
        query = query.filter(BillingInvoice.institution_id == institution_id)
    return query.limit(limit).all()


def generate_invoice(
    db: Session,
    *,
    institution: Institution,
    period_start: datetime,
    period_end: datetime,
    note: str | None = None,
) -> BillingInvoice:
    if period_end <= period_start:
        raise ValueError("period_end must be after period_start")
    rows = (
        db.query(Disbursement)
        .join(FinancingApplication, Disbursement.application_id == FinancingApplication.id)
        .filter(
            FinancingApplication.institution_id == institution.id,
            Disbursement.disbursed_at >= period_start,
            Disbursement.disbursed_at < period_end,
        )
        .all()
    )
    volume = sum((Decimal(str(row.amount or 0)) for row in rows), Decimal("0"))
    fee_bps = int(getattr(institution, "billing_fee_bps", 25) or 0)
    fee = (volume * Decimal(fee_bps) / Decimal("10000")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    invoice = BillingInvoice(
        institution_id=institution.id,
        period_start=period_start,
        period_end=period_end,
        transaction_count=len(rows),
        volume_amount=volume.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
        fee_bps=fee_bps,
        fee_amount=fee,
        currency="KES",
        status="issued",
        note=(note or "").strip() or None,
    )
    db.add(invoice)
    db.flush()
    log_audit(
        db,
        entity_type="billing_invoice",
        entity_id=invoice.id,
        actor=AuditActor.HUMAN,
        action="billing.issued",
        details=f"count={len(rows)}, volume={volume}, fee={fee}, bps={fee_bps}",
    )
    db.flush()
    return invoice


def mark_paid(db: Session, invoice: BillingInvoice) -> BillingInvoice:
    if invoice.status == "paid":
        return invoice
    invoice.status = "paid"
    invoice.paid_at = datetime.now(timezone.utc)
    log_audit(
        db,
        entity_type="billing_invoice",
        entity_id=invoice.id,
        actor=AuditActor.HUMAN,
        action="billing.paid",
        details=f"fee={invoice.fee_amount}",
    )
    db.flush()
    return invoice


def invoice_to_dict(invoice: BillingInvoice, institution_name: str | None = None) -> dict[str, Any]:
    return {
        "id": invoice.id,
        "institution_id": invoice.institution_id,
        "institution_name": institution_name,
        "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
        "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
        "transaction_count": invoice.transaction_count,
        "volume_amount": str(invoice.volume_amount),
        "fee_bps": invoice.fee_bps,
        "fee_amount": str(invoice.fee_amount),
        "currency": invoice.currency,
        "status": invoice.status,
        "issued_at": invoice.issued_at.isoformat() if invoice.issued_at else None,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "note": invoice.note,
    }
