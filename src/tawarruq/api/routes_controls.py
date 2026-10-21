"""Approvals, billing, reconciliation, and exception-retry APIs."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tawarruq.api.deps import (
    require_approve_txn,
    require_export_data,
    require_manage_billing,
    require_reconcile,
    require_tenant_access,
    require_write_bti_ops,
    tenant_filter_institution_id,
)
from tawarruq.database import get_db
from tawarruq.models.controls import BillingInvoice, PendingApproval, ReconciliationItem
from tawarruq.models.institution import Institution
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services import billing_service, reconciliation_service
from tawarruq.services.approval_service import approve_pending, list_approvals, reject_pending
from tawarruq.services.kenya_ops_service import retry_kenya_case

router = APIRouter()


class ApprovalDecision(BaseModel):
    note: str | None = None


class BillingGenerateRequest(BaseModel):
    institution_id: str
    period_start: datetime
    period_end: datetime
    note: str | None = None


class ReconciliationResolve(BaseModel):
    status: str = Field(..., description="matched | exception | outstanding")
    note: str | None = None


def _institution_name(db: Session, institution_id: str | None) -> str | None:
    if not institution_id:
        return None
    institution = db.get(Institution, institution_id)
    return institution.name if institution else None


def _approval_dict(db: Session, item: PendingApproval) -> dict:
    return {
        "id": item.id,
        "institution_id": item.institution_id,
        "institution_name": _institution_name(db, item.institution_id),
        "step": item.step,
        "action": item.action,
        "status": item.status,
        "amount": str(item.amount) if item.amount is not None else None,
        "currency": item.currency,
        "application_id": item.application_id,
        "transaction_id": item.transaction_id,
        "requested_by_id": item.requested_by_id,
        "decided_by_id": item.decided_by_id,
        "decision_note": item.decision_note,
        "last_error": item.last_error,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "decided_at": item.decided_at.isoformat() if item.decided_at else None,
        "queued": item.status == "pending",
    }


@router.get("/ops/approvals", tags=["Approvals"], summary="Maker-checker queue")
def get_approvals(
    request: Request,
    status: str | None = Query("pending"),
    institution_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    require_approve_txn(request)
    scoped = tenant_filter_institution_id(request, institution_id)
    return [_approval_dict(db, item) for item in list_approvals(db, institution_id=scoped, status=status)]


@router.post("/ops/approvals/{approval_id}/approve", tags=["Approvals"], summary="Approve and execute")
def post_approve(
    approval_id: str, payload: ApprovalDecision, request: Request, db: Session = Depends(get_db)
) -> dict:
    require_approve_txn(request)
    approval = db.get(PendingApproval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    require_tenant_access(request, approval.institution_id)
    try:
        updated = approve_pending(db, request, approval, note=payload.note)
        db.commit()
        db.refresh(updated)
        return _approval_dict(db, updated)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ops/approvals/{approval_id}/reject", tags=["Approvals"], summary="Reject queued step")
def post_reject(
    approval_id: str, payload: ApprovalDecision, request: Request, db: Session = Depends(get_db)
) -> dict:
    require_approve_txn(request)
    approval = db.get(PendingApproval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    require_tenant_access(request, approval.institution_id)
    try:
        updated = reject_pending(db, request, approval, note=payload.note)
        db.commit()
        db.refresh(updated)
        return _approval_dict(db, updated)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ops/billing/invoices", tags=["Billing"], summary="List platform invoices")
def get_invoices(
    request: Request, institution_id: str | None = None, db: Session = Depends(get_db)
) -> list[dict]:
    require_manage_billing(request)
    scoped = tenant_filter_institution_id(request, institution_id)
    invoices = billing_service.list_invoices(db, institution_id=scoped)
    return [billing_service.invoice_to_dict(item, _institution_name(db, item.institution_id)) for item in invoices]


@router.post("/ops/billing/invoices", tags=["Billing"], summary="Generate a usage invoice", status_code=201)
def post_invoice(payload: BillingGenerateRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    require_manage_billing(request)
    require_tenant_access(request, payload.institution_id)
    institution = db.get(Institution, payload.institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    try:
        invoice = billing_service.generate_invoice(
            db,
            institution=institution,
            period_start=payload.period_start,
            period_end=payload.period_end,
            note=payload.note,
        )
        db.commit()
        db.refresh(invoice)
        return billing_service.invoice_to_dict(invoice, institution.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ops/billing/invoices/{invoice_id}/pay", tags=["Billing"], summary="Mark invoice paid")
def post_pay_invoice(invoice_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    require_manage_billing(request)
    invoice = db.get(BillingInvoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    require_tenant_access(request, invoice.institution_id)
    billing_service.mark_paid(db, invoice)
    db.commit()
    db.refresh(invoice)
    return billing_service.invoice_to_dict(invoice, _institution_name(db, invoice.institution_id))


@router.get("/ops/billing/invoices/export", tags=["Billing"], summary="Export invoices CSV")
def export_invoices(request: Request, institution_id: str | None = None, db: Session = Depends(get_db)):
    from fastapi.responses import Response

    require_manage_billing(request)
    require_export_data(request)
    scoped = tenant_filter_institution_id(request, institution_id)
    invoices = billing_service.list_invoices(db, institution_id=scoped, limit=5000)
    lines = ["id,institution_id,period_start,period_end,volume,fee_bps,fee_amount,status"]
    for item in invoices:
        lines.append(
            f"{item.id},{item.institution_id},{item.period_start},{item.period_end},"
            f"{item.volume_amount},{item.fee_bps},{item.fee_amount},{item.status}"
        )
    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=billing_invoices.csv"},
    )


@router.post("/ops/reconciliation/scan", tags=["Reconciliation"], summary="Scan trades vs settlement")
def post_recon_scan(
    request: Request, institution_id: str | None = None, db: Session = Depends(get_db)
) -> dict:
    require_reconcile(request)
    scoped = tenant_filter_institution_id(request, institution_id)
    created = reconciliation_service.scan_reconciliation(db, institution_id=scoped)
    db.commit()
    return {"scanned": True, "created_or_updated": len(created)}


@router.get("/ops/reconciliation", tags=["Reconciliation"], summary="Reconciliation items")
def get_recon(
    request: Request,
    status: str | None = None,
    institution_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    require_reconcile(request)
    scoped = tenant_filter_institution_id(request, institution_id)
    items = reconciliation_service.list_items(db, institution_id=scoped, status=status)
    return [
        reconciliation_service.item_to_dict(item, _institution_name(db, item.institution_id)) for item in items
    ]


@router.post("/ops/reconciliation/{item_id}/resolve", tags=["Reconciliation"], summary="Resolve exception")
def post_recon_resolve(
    item_id: str, payload: ReconciliationResolve, request: Request, db: Session = Depends(get_db)
) -> dict:
    require_reconcile(request)
    item = db.get(ReconciliationItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Reconciliation item not found")
    require_tenant_access(request, item.institution_id)
    try:
        updated = reconciliation_service.resolve_item(
            db,
            item,
            status=payload.status,
            note=payload.note,
            actor_id=getattr(request.state, "ops_user_id", None),
        )
        db.commit()
        db.refresh(updated)
        return reconciliation_service.item_to_dict(updated, _institution_name(db, updated.institution_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ops/reconciliation/export", tags=["Reconciliation"], summary="Export reconciliation CSV")
def export_recon(request: Request, institution_id: str | None = None, db: Session = Depends(get_db)):
    from fastapi.responses import Response

    require_reconcile(request)
    require_export_data(request)
    scoped = tenant_filter_institution_id(request, institution_id)
    items = reconciliation_service.list_items(db, institution_id=scoped, limit=5000)
    lines = ["id,institution_id,transaction_id,expected,settled,status"]
    for item in items:
        lines.append(
            f"{item.id},{item.institution_id},{item.transaction_id},{item.expected_amount},{item.settled_amount},{item.status}"
        )
    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reconciliation.csv"},
    )


@router.post(
    "/kenya/ops/cases/{application_id}/retry",
    tags=["Kenya Ops"],
    summary="BTI ops: reset failed Kenya legs for retry",
)
def kenya_retry(application_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    require_write_bti_ops(request)
    from tawarruq.api.kenya_access import guarded_application

    application = guarded_application(db, request, application_id)
    try:
        result = retry_kenya_case(db, application)
        db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/manual-bridge/transactions/{transaction_id}/retry",
    tags=["Malaysia Manual Bridge"],
    summary="BTI ops: reset failed manual-bridge legs for retry",
)
def manual_bridge_retry(transaction_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    require_write_bti_ops(request)
    txn = db.get(CommodityTransaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    require_tenant_access(request, txn.institution_id)
    from tawarruq.enums import AuditActor, LegStatus, TransactionStatus
    from tawarruq.services.audit_service import log_audit

    reset = 0
    for leg in txn.legs:
        if leg.status == LegStatus.FAILED:
            leg.status = LegStatus.PENDING
            leg.error_message = None
            reset += 1
    if txn.status == TransactionStatus.FAILED:
        txn.status = TransactionStatus.AWAITING_MANUAL
    log_audit(
        db,
        entity_type="transaction",
        entity_id=txn.id,
        actor=AuditActor.HUMAN,
        action="bti.retry",
        details=f"reset_legs={reset}",
    )
    db.commit()
    return {"transaction_id": txn.id, "reset_legs": reset, "message": "Failed legs reset for retry"}
