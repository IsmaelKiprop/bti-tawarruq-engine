"""Maker-checker queue for Murabaha, liquidation, and disbursement."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from tawarruq.enums import ApiKeyRole, AuditActor
from tawarruq.models.application import FinancingApplication
from tawarruq.models.controls import PendingApproval
from tawarruq.models.institution import Institution
from tawarruq.models.ops_user import OpsUser
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.audit_service import log_audit
from tawarruq.services.rbac import auth_is_enabled, get_request_role, require_permission

DEFAULT_APPROVAL_STEPS = ("murabaha", "liquidation", "disbursement")

ACTION_STEP: dict[str, str] = {
    "kenya.accept_offer": "murabaha",
    "kenya.create_murabaha": "murabaha",
    "application.accept_offer": "murabaha",
    "kenya.liquidate": "liquidation",
    "malaysia.sale_leg": "liquidation",
    "kenya.complete_settlement": "disbursement",
    "kenya.disburse": "disbursement",
    "malaysia.disburse": "disbursement",
    "kenya.run_full_flow": "disbursement",
    "malaysia.run_full_flow": "disbursement",
}


def parse_approval_steps(raw: str | None) -> set[str]:
    if not raw:
        return set(DEFAULT_APPROVAL_STEPS)
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def require_institution_active(db: Session, institution_id: str | None) -> Institution | None:
    if not institution_id:
        return None
    institution = db.get(Institution, institution_id)
    if institution is not None and not getattr(institution, "active", True):
        raise HTTPException(status_code=403, detail="Institution is suspended")
    return institution


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _effective_limit(institution: Institution | None, approver: OpsUser | None) -> Decimal | None:
    limits: list[Decimal] = []
    inst_limit = _to_decimal(getattr(institution, "approval_limit_amount", None) if institution else None)
    user_limit = _to_decimal(getattr(approver, "approval_limit_amount", None) if approver else None)
    if inst_limit is not None:
        limits.append(inst_limit)
    if user_limit is not None:
        limits.append(user_limit)
    if not limits:
        return None
    return min(limits)


def _serialize(approval: PendingApproval) -> dict[str, Any]:
    return {
        "queued": True,
        "approval_id": approval.id,
        "id": approval.id,
        "step": approval.step,
        "action": approval.action,
        "status": approval.status,
        "amount": str(approval.amount) if approval.amount is not None else None,
        "currency": approval.currency,
        "application_id": approval.application_id,
        "transaction_id": approval.transaction_id,
        "message": "Queued for FI Approver (maker-checker). The initiator cannot be the sole approver.",
    }


def maybe_queue(
    db: Session,
    request: Request,
    *,
    action: str,
    institution_id: str,
    amount: Any = None,
    application_id: str | None = None,
    transaction_id: str | None = None,
    payload: dict[str, Any] | None = None,
    currency: str = "KES",
) -> dict[str, Any] | None:
    """Return a queued payload (caller should HTTP 202) or None to execute immediately."""
    if action not in ACTION_STEP:
        raise ValueError(f"Unknown approval action: {action}")
    if not auth_is_enabled(request):
        return None
    if getattr(request.state, "auth_method", None) == "mobile":
        return None
    role = get_request_role(request)
    if role == ApiKeyRole.API_CLIENT:
        return None

    institution = require_institution_active(db, institution_id)
    step = ACTION_STEP[action]
    required = parse_approval_steps(getattr(institution, "approval_steps", None) if institution else None)
    require_permission(request, "write_ops")
    if step not in required:
        return None

    existing = (
        db.query(PendingApproval)
        .filter(
            PendingApproval.institution_id == institution_id,
            PendingApproval.action == action,
            PendingApproval.status == "pending",
            PendingApproval.application_id == application_id,
            PendingApproval.transaction_id == transaction_id,
        )
        .first()
    )
    if existing:
        return _serialize(existing)

    application = db.get(FinancingApplication, application_id) if application_id else None
    resolved_currency = currency
    if application and application.currency:
        resolved_currency = application.currency
    resolved_amount = _to_decimal(amount)
    if resolved_amount is None and application is not None:
        resolved_amount = _to_decimal(application.amount_requested)

    approval = PendingApproval(
        institution_id=institution_id,
        step=step,
        action=action,
        status="pending",
        amount=resolved_amount,
        currency=resolved_currency,
        application_id=application_id,
        transaction_id=transaction_id,
        payload_json=json.dumps(payload or {}, default=str),
        requested_by_id=getattr(request.state, "ops_user_id", None),
    )
    db.add(approval)
    db.flush()
    log_audit(
        db,
        entity_type="pending_approval",
        entity_id=approval.id,
        actor=AuditActor.HUMAN,
        action="approval.queued",
        details=f"step={step}, action={action}, application={application_id}",
    )
    db.commit()
    db.refresh(approval)
    return _serialize(approval)


def list_approvals(
    db: Session,
    *,
    institution_id: str | None,
    status: str | None = "pending",
    limit: int = 200,
) -> list[PendingApproval]:
    query = db.query(PendingApproval).order_by(PendingApproval.created_at.desc())
    if institution_id:
        query = query.filter(PendingApproval.institution_id == institution_id)
    if status:
        query = query.filter(PendingApproval.status == status)
    return query.limit(limit).all()


def _load_payload(approval: PendingApproval) -> dict[str, Any]:
    try:
        data = json.loads(approval.payload_json or "{}")
    except json.JSONDecodeError:
        data = {}
    if approval.application_id:
        data.setdefault("application_id", approval.application_id)
    if approval.transaction_id:
        data.setdefault("transaction_id", approval.transaction_id)
    return data


def _executors() -> dict[str, Callable[[Session, dict[str, Any]], Any]]:
    from tawarruq.services import application_service, malaysia_flow_service, transaction_service
    from tawarruq.services.kenya_flow_service import (
        complete_kenya_disbursement,
        execute_liquidation_leg,
        run_ordered_kenya_flow,
    )
    from tawarruq.services.repayment_service import create_murabaha_contract

    def _sale_leg(db: Session, payload: dict[str, Any]) -> Any:
        from tawarruq.amanah.worker import AmanahWorker

        transaction = db.get(CommodityTransaction, payload["transaction_id"])
        if not transaction:
            raise ValueError("Transaction not found")
        worker = AmanahWorker(write_enabled=True)
        worker.process_transaction(db, transaction)
        return transaction_service.get_transaction_detail(db, payload["transaction_id"])

    return {
        "kenya.accept_offer": lambda db, p: application_service.accept_offer(db, p["application_id"]),
        "kenya.create_murabaha": lambda db, p: create_murabaha_contract(db, p["application_id"]),
        "application.accept_offer": lambda db, p: application_service.accept_offer(db, p["application_id"]),
        "kenya.liquidate": lambda db, p: execute_liquidation_leg(db, p["transaction_id"]),
        "malaysia.sale_leg": _sale_leg,
        "kenya.complete_settlement": lambda db, p: _execute_kenya_settlement(db, p),
        "kenya.disburse": lambda db, p: complete_kenya_disbursement(
            db, application_id=p["application_id"], transaction_id=p["transaction_id"]
        ),
        "malaysia.disburse": lambda db, p: transaction_service.create_disbursement(
            db, application_id=p["application_id"], transaction_id=p["transaction_id"]
        ),
        "kenya.run_full_flow": lambda db, p: run_ordered_kenya_flow(db, p["application_id"]),
        "malaysia.run_full_flow": lambda db, p: malaysia_flow_service.run_ordered_malaysia_flow(db, p["application_id"]),
    }


def _execute_kenya_settlement(db: Session, payload: dict[str, Any]) -> Any:
    from tawarruq.enums import LegNumber
    from tawarruq.services.kenya_flow_service import (
        complete_kenya_disbursement,
        execute_liquidation_leg,
        execute_transfer_leg,
        get_mno_transaction,
    )

    application_id = payload["application_id"]
    txn = get_mno_transaction(db, application_id)
    if not txn:
        raise ValueError("MNO transaction not found")
    transfer = next((leg for leg in txn.legs if str(leg.leg_number) == LegNumber.TRANSFER), None)
    if transfer and transfer.status == "pending":
        execute_transfer_leg(db, txn.id)
    execute_liquidation_leg(db, txn.id)
    return complete_kenya_disbursement(db, application_id=application_id, transaction_id=txn.id)


def approve_pending(
    db: Session,
    request: Request,
    approval: PendingApproval,
    *,
    note: str | None = None,
) -> PendingApproval:
    require_permission(request, "approve_txn")
    if approval.status != "pending":
        raise ValueError("Approval is no longer pending")
    actor_id = getattr(request.state, "ops_user_id", None)
    if actor_id and approval.requested_by_id and actor_id == approval.requested_by_id:
        raise ValueError("Maker-checker: you cannot approve a request you initiated")

    institution = require_institution_active(db, approval.institution_id)
    approver = db.get(OpsUser, actor_id) if actor_id else None
    limit = _effective_limit(institution, approver)
    amount = _to_decimal(approval.amount)
    if limit is not None and amount is not None and amount > limit:
        raise ValueError(f"Amount {amount} exceeds approval limit {limit}")

    executor = _executors().get(approval.action)
    if not executor:
        raise ValueError(f"No executor for action {approval.action}")
    try:
        executor(db, _load_payload(approval))
    except Exception as exc:
        approval.last_error = str(exc)
        db.flush()
        raise
    approval.status = "executed"
    approval.decided_by_id = actor_id
    approval.decision_note = (note or "").strip() or None
    approval.decided_at = datetime.now(timezone.utc)
    log_audit(
        db,
        entity_type="pending_approval",
        entity_id=approval.id,
        actor=AuditActor.HUMAN,
        action="approval.executed",
        details=f"step={approval.step}, action={approval.action}",
    )
    db.flush()
    return approval


def reject_pending(
    db: Session,
    request: Request,
    approval: PendingApproval,
    *,
    note: str | None = None,
) -> PendingApproval:
    require_permission(request, "approve_txn")
    if approval.status != "pending":
        raise ValueError("Approval is no longer pending")
    actor_id = getattr(request.state, "ops_user_id", None)
    if actor_id and approval.requested_by_id and actor_id == approval.requested_by_id:
        raise ValueError("Maker-checker: you cannot reject a request you initiated as the sole checker")
    approval.status = "rejected"
    approval.decided_by_id = actor_id
    approval.decision_note = (note or "").strip() or "Rejected"
    approval.decided_at = datetime.now(timezone.utc)
    log_audit(
        db,
        entity_type="pending_approval",
        entity_id=approval.id,
        actor=AuditActor.HUMAN,
        action="approval.rejected",
        details=approval.decision_note,
    )
    db.flush()
    return approval
