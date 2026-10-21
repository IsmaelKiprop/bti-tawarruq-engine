from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from tawarruq.enums import LegStatus, TransactionMode
from tawarruq.models.application import FinancingApplication
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.kenya_flow import LiquidationOrder, MurabahaContract, RepaymentInstallment, ThirdPartyBroker
from tawarruq.models.transaction import CommodityTransaction, TransactionLeg
from tawarruq.services.customer_notify_service import customer_journey_url
from tawarruq.services.shariah_state_machine import possession_is_cryptographically_sealed

_KENYA_TXN_MODES = (TransactionMode.MNO.value, TransactionMode.AGENT_DEALER.value)


def _leg(txn: CommodityTransaction | None, number: str) -> TransactionLeg | None:
    if not txn or not txn.legs:
        return None
    for leg in txn.legs:
        if str(leg.leg_number) == str(number):
            return leg
    return None


def _resolve_next_action(
    app: FinancingApplication,
    txn: CommodityTransaction | None,
    sealed: bool,
) -> tuple[str, str]:
    if not app.eligibility_passed:
        return ("eligibility", "Run or record eligibility decision")
    if not txn:
        return ("purchase", "Initiate commodity purchase (Leg 1)")
    leg1 = _leg(txn, "1")
    if not leg1 or leg1.status != LegStatus.CONFIRMED:
        if leg1 and leg1.status == LegStatus.AWAITING_POSSESSION:
            return ("possession", "Confirm constructive possession (supplier receipt)")
        return ("purchase", "Initiate commodity purchase (Leg 1)")
    if not sealed:
        return ("possession", "Confirm constructive possession (supplier receipt)")
    if not app.offer:
        return ("offer", "Generate Murabaha cost-plus offer")
    if not app.offer.accepted_at:
        return ("accept", "Awaiting customer acceptance of Murabaha offer")
    if not app.murabaha_contract:
        return ("murabaha", "Create Murabaha contract")
    if not app.murabaha_contract.signed_at:
        return ("sign", "Awaiting customer digital signature")
    leg2 = _leg(txn, "2")
    if not leg2 or leg2.status != LegStatus.CONFIRMED:
        return ("transfer", "Transfer ownership Financier → Customer")
    if not app.customer_agency:
        return ("wakala", "Record Wakala consent (required before liquidation)")
    leg3 = _leg(txn, "3")
    if not leg3 or leg3.status != LegStatus.CONFIRMED:
        return ("liquidate", "Liquidate via independent broker (No-Inah)")
    wallet_ok = any(
        d.wallet_disbursement and d.wallet_disbursement.status == "credited"
        for d in app.disbursements
    )
    if not wallet_ok:
        return ("disburse", "Credit customer wallet and create repayment schedule")
    installments = app.murabaha_contract.installments if app.murabaha_contract else []
    unpaid = [i for i in installments if i.status != "paid"]
    if unpaid:
        return ("repay", f"Collect repayments ({len(unpaid)} outstanding)")
    return ("complete", "Journey complete")


def build_kenya_case(db: Session, application: FinancingApplication) -> dict[str, Any]:
    txn = None
    for candidate in application.transactions:
        if candidate.mode in _KENYA_TXN_MODES:
            txn = candidate
            break
    if not txn and application.transactions:
        txn = application.transactions[-1]

    sealed = bool(txn and possession_is_cryptographically_sealed(db, txn))
    action_code, action_label = _resolve_next_action(application, txn, sealed)

    batch = None
    leg1 = _leg(txn, "1")
    if leg1 and getattr(leg1, "asset_batch", None):
        batch = leg1.asset_batch

    liquidation = txn.liquidation_order if txn else None
    broker = liquidation.broker if liquidation else None

    wallet = None
    for disb in application.disbursements:
        if disb.wallet_disbursement:
            wallet = disb.wallet_disbursement
            break

    if application.murabaha_contract:
        installments = sorted(application.murabaha_contract.installments, key=lambda x: x.installment_number)
    else:
        installments = []
    paid = sum(1 for i in installments if i.status == "paid")
    customer = application.customer

    case = {
        "application_id": application.id,
        "institution_id": application.institution_id,
        "customer_ref": application.customer_ref,
        "customer_name": customer.full_name if customer else application.customer_ref,
        "customer_phone": customer.phone if customer else None,
        "customer_email": customer.email if customer else None,
        "journey_url": customer_journey_url(application.customer_ref),
        "wallet_number": customer.wallet_number if customer else None,
        "amount_requested": str(application.amount_requested),
        "term_months": application.term_months,
        "purpose": application.purpose,
        "status": application.status,
        "current_phase": application.current_phase,
        "eligibility_passed": application.eligibility_passed,
        "offer_accepted": bool(application.offer and application.offer.accepted_at),
        "murabaha_signed": bool(application.murabaha_contract and application.murabaha_contract.signed_at),
        "wakala_appointed": application.customer_agency is not None,
        "wakala_notes": application.customer_agency.notes if application.customer_agency else None,
        "possession_sealed": sealed,
        "transaction_id": txn.id if txn else None,
        "transaction_status": txn.status if txn else None,
        "transaction_phase": txn.phase if txn else None,
        "transaction_mode": txn.mode if txn else None,
        "commodity_code": txn.commodity_code if txn else None,
        "batch_id": batch.batch_id if batch else None,
        "asset_ref_hash": batch.asset_ref_hash if batch else None,
        "mno_receipt_id": batch.mno_receipt_id if batch else None,
        "possession_status": batch.possession_status if batch else None,
        "broker_code": broker.code if broker else None,
        "broker_name": broker.name if broker else None,
        "broker_is_mno_pool": broker.is_mno_pool if broker else None,
        "no_inah_validated": liquidation.no_inah_validated if liquidation else None,
        "liquidation_spot_amount": str(liquidation.spot_amount) if (liquidation and liquidation.spot_amount is not None) else None,
        "wallet_status": wallet.status if wallet else None,
        "wallet_provider": wallet.provider if wallet else None,
        "wallet_external_txn_id": wallet.external_txn_id if wallet else None,
        "wallet_credited": bool(wallet and wallet.status == "credited"),
        "installments_total": len(installments),
        "installments_paid": paid,
        "next_action": action_code,
        "next_action_label": action_label,
        "created_at": application.created_at.isoformat() if application.created_at else None,
        "offer": {
            "cost_price": str(application.offer.cost_price),
            "profit_amount": str(application.offer.profit_amount),
            "total_payable": str(application.offer.total_payable),
            "accepted": bool(application.offer.accepted_at),
        } if application.offer else None,
        "legs": [
            {
                "leg_number": leg.leg_number,
                "status": leg.status,
                "external_ref": leg.external_ref,
            }
            for leg in sorted(txn.legs, key=lambda l: l.leg_number)
        ] if txn else [],
    }
    return case


def _kenya_query(db: Session):
    return (
        db.query(FinancingApplication)
        .options(
            joinedload(FinancingApplication.customer),
            joinedload(FinancingApplication.offer),
            joinedload(FinancingApplication.customer_agency),
            joinedload(FinancingApplication.murabaha_contract).joinedload(MurabahaContract.installments),
            joinedload(FinancingApplication.disbursements).joinedload(Disbursement.wallet_disbursement),
            joinedload(FinancingApplication.transactions).joinedload(CommodityTransaction.legs).joinedload(TransactionLeg.asset_batch),
            joinedload(FinancingApplication.transactions).joinedload(CommodityTransaction.liquidation_order).joinedload(LiquidationOrder.broker),
        )
        .order_by(FinancingApplication.created_at.desc())
    )


def list_kenya_ops_cases(
    db: Session,
    institution_id: str | None = None,
    queue: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    apps = _kenya_query(db).limit(limit * 3).all()
    cases = []
    for app in apps:
        is_kenya = bool(app.customer_id) or any(t.mode in _KENYA_TXN_MODES for t in app.transactions)
        if not is_kenya:
            continue
        if institution_id and app.institution_id != institution_id:
            continue
        case = build_kenya_case(db, app)
        if queue == "possession" and case["next_action"] != "possession":
            continue
        if queue == "wakala" and case["next_action"] != "wakala":
            continue
        if queue == "settlement" and case["next_action"] not in frozenset({"liquidate", "disburse", "transfer"}):
            continue
        if queue == "repay" and case["next_action"] != "repay":
            continue
        if queue == "active" and case["next_action"] == "complete":
            continue
        cases.append(case)
        if len(cases) >= limit:
            break
    return cases


def get_kenya_ops_case(db: Session, application_id: str) -> dict[str, Any] | None:
    app = _kenya_query(db).filter(FinancingApplication.id == application_id).first()
    if not app:
        return None
    return build_kenya_case(db, app)


def list_repayment_board(
    db: Session,
    institution_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = (
        db.query(RepaymentInstallment)
        .join(MurabahaContract)
        .join(FinancingApplication)
        .options(
            joinedload(RepaymentInstallment.contract)
            .joinedload(MurabahaContract.application)
            .joinedload(FinancingApplication.customer)
        )
        .order_by(RepaymentInstallment.due_date.asc())
        .limit(limit)
        .all()
    )
    now = datetime.now(timezone.utc)
    board = []
    for inst in rows:
        app = inst.contract.application
        if institution_id and app.institution_id != institution_id:
            continue
        due = inst.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        overdue = (inst.status != "paid") and (due < now)
        board.append(
            {
                "installment_id": inst.id,
                "application_id": app.id,
                "customer_ref": app.customer_ref,
                "customer_name": app.customer.full_name if app.customer else app.customer_ref,
                "installment_number": inst.installment_number,
                "due_date": inst.due_date.isoformat() if inst.due_date else None,
                "amount": str(inst.amount),
                "status": "overdue" if overdue else inst.status,
                "paid_at": inst.paid_at.isoformat() if inst.paid_at else None,
                "payment_ref": inst.payment_ref,
            }
        )
    return board


def retry_kenya_case(db: Session, application: FinancingApplication) -> dict[str, Any]:
    """Reset failed legs so BTI ops can re-run the next Kenya step (audited)."""
    from tawarruq.enums import AuditActor, LegStatus, TransactionStatus
    from tawarruq.services.audit_service import log_audit

    txn = None
    for candidate in application.transactions:
        if candidate.mode in _KENYA_TXN_MODES:
            txn = candidate
            break
    if not txn and application.transactions:
        txn = application.transactions[-1]
    reset = 0
    if txn:
        for leg in txn.legs:
            if leg.status == LegStatus.FAILED:
                leg.status = LegStatus.PENDING
                leg.error_message = None
                reset += 1
        if txn.status == TransactionStatus.FAILED:
            txn.status = TransactionStatus.CREATED
    log_audit(
        db,
        entity_type="application",
        entity_id=application.id,
        actor=AuditActor.HUMAN,
        action="bti.retry",
        details=f"reset_legs={reset}",
    )
    db.flush()
    return {
        "application_id": application.id,
        "transaction_id": txn.id if txn else None,
        "reset_legs": reset,
        "message": "Failed Kenya legs reset for retry",
    }


def list_brokers(db: Session) -> list[dict[str, Any]]:
    brokers = db.query(ThirdPartyBroker).order_by(ThirdPartyBroker.code).all()
    return [
        {
            "id": b.id,
            "code": b.code,
            "name": b.name,
            "is_mno_pool": b.is_mno_pool,
            "active": b.active,
            "eligible_for_liquidation": b.active and not b.is_mno_pool,
        }
        for b in brokers
    ]
