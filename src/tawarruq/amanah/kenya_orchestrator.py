from sqlalchemy.orm import Session

from tawarruq.enums import (
    ApplicationStatus,
    AuditActor,
    LegNumber,
    LegStatus,
    TransactionMode,
    TransactionStatus,
)
from tawarruq.models.application import FinancingApplication
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.audit_service import log_audit
from tawarruq.services.business_flow_service import appoint_wakala_with_customer_consent
from tawarruq.services.kenya_flow_service import (
    complete_kenya_disbursement,
    create_mno_transaction,
    execute_liquidation_leg,
    execute_mno_purchase_leg,
    execute_transfer_leg,
    get_mno_transaction,
    prepare_murabaha_for_application,
    require_possession_before_murabaha_offer,
    verify_possession,
)


def is_kenya_application(application: FinancingApplication) -> bool:
    return bool(application.customer_id)


def auto_create_kenya_transaction(db: Session, application: FinancingApplication) -> CommodityTransaction | None:
    if get_mno_transaction(db, application.id):
        return None
    txn = create_mno_transaction(db, application_id=application.id, actor=AuditActor.AI_WORKER)
    log_audit(
        db,
        entity_type="financing_application",
        entity_id=application.id,
        actor=AuditActor.AI_WORKER,
        action="transaction.auto_created",
        details=f"mode={txn.mode} commodity={txn.commodity_code}",
    )
    return txn


def _all_legs_before_sale_confirmed(transaction: CommodityTransaction) -> bool:
    for leg in transaction.legs:
        if leg.leg_number in (LegNumber.PURCHASE, LegNumber.TRANSFER):
            if leg.status != LegStatus.CONFIRMED:
                return False
    return True


def _process_mno_mock_sync(db: Session, transaction: CommodityTransaction) -> None:
    application = db.get(FinancingApplication, transaction.application_id)
    if not application:
        return

    leg_map = {leg.leg_number: leg for leg in transaction.legs}
    leg1 = leg_map.get(LegNumber.PURCHASE)
    leg2 = leg_map.get(LegNumber.TRANSFER)
    leg3 = leg_map.get(LegNumber.SALE)

    if leg1 and leg1.status == LegStatus.PENDING:
        execute_mno_purchase_leg(db, transaction.id, actor=AuditActor.AI_WORKER)
        db.flush()
        return

    if leg1 and leg1.status == LegStatus.AWAITING_POSSESSION:
        verify_possession(db, transaction.id, actor=AuditActor.AI_WORKER)
        db.flush()
        return

    if not application.offer:
        from tawarruq.services import application_service

        application_service.create_offer(db, application.id)
        db.flush()
        return

    if not application.offer.accepted_at:
        from tawarruq.services import application_service

        application_service.accept_offer(db, application.id)
        db.flush()
        return

    if not application.murabaha_contract or not application.murabaha_contract.signed_at:
        prepare_murabaha_for_application(db, application.id)
        db.flush()
        return

    if leg2 and leg2.status == LegStatus.PENDING:
        execute_transfer_leg(db, transaction.id, actor=AuditActor.AI_WORKER)
        db.flush()
        return

    if not application.customer_agency:
        appoint_wakala_with_customer_consent(
            db,
            application.id,
            consent_ref="amanah-auto-wakala",
            actor=AuditActor.AI_WORKER,
        )
        db.flush()
        return

    if leg3 and leg3.status == LegStatus.PENDING:
        execute_liquidation_leg(db, transaction.id, actor=AuditActor.AI_WORKER)
        db.flush()
        return

    has_wallet_disbursement = any(d.wallet_disbursement for d in application.disbursements)
    if not has_wallet_disbursement:
        complete_kenya_disbursement(
            db,
            application_id=application.id,
            transaction_id=transaction.id,
            actor=AuditActor.AI_WORKER,
        )
        db.flush()

    transaction.status = TransactionStatus.COMPLETED
    application.status = ApplicationStatus.COMPLETED


def process_mno_transaction(
    db: Session,
    transaction: CommodityTransaction,
    *,
    write_enabled: bool = True,
) -> None:
    if not write_enabled:
        return
    if transaction.status in (TransactionStatus.COMPLETED, TransactionStatus.FAILED, TransactionStatus.ESCALATED):
        return
    _process_mno_mock_sync(db, transaction)
