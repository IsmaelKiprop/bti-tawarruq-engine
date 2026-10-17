from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from tawarruq.enums import (
    ApplicationStatus,
    AuditActor,
    CommodityType,
    LegNumber,
    LegStatus,
    PossessionStatus,
    ShariahStepId,
    TransactionMode,
    TransactionPhase,
    TransactionStatus,
    WebhookEvent,
)
from tawarruq.mno.base import MnoPurchaseRequest, MnoPurchaseResult, PossessionVerifyRequest
from tawarruq.mno.factory import get_mno_backend
from tawarruq.services.integration_config_service import resolve_integration_profile
from tawarruq.models.application import FinancingApplication
from tawarruq.models.kenya_flow import AgentDealer, AgentDealerFloatTopup, AssetBatch, LiquidationOrder
from tawarruq.models.transaction import CommodityTransaction, TransactionLeg
from tawarruq.services.audit_service import log_audit
from tawarruq.integrations.broker.liquidator import BrokerLiquidationRequest, get_broker_client
from tawarruq.services.business_flow_service import appoint_wakala_with_customer_consent, record_customer_sale
from tawarruq.services.no_inah_service import select_broker_for_commodity, validate_no_inah
from tawarruq.services.trade_evidence_service import issue_trade_documents
from tawarruq.services.customer_notify_service import notify_trade_documents_ready
from tawarruq.services.repayment_service import create_murabaha_contract, generate_repayment_schedule, sign_murabaha_contract
from tawarruq.services.shariah_audit_service import log_shariah_step
from tawarruq.services.shariah_state_machine import (
    ShariahStateViolation,
    advance_phase,
    validate_liquidation_allowed,
    validate_transfer_allowed,
)
from tawarruq.services.transaction_service import (
    create_disbursement,
    refresh_transaction_status,
    update_leg_from_execution,
)
from tawarruq.services.wallet_service import credit_wallet
from tawarruq.services.webhook_service import dispatch_webhook_event


def _log_constructive_possession(
    db: Session,
    *,
    batch: AssetBatch,
    transaction: CommodityTransaction,
    application: FinancingApplication | None,
    verified_at: datetime,
) -> None:
    log_shariah_step(
        db,
        step_id=ShariahStepId.CONSTRUCTIVE_POSSESSION,
        entity_type="asset_batch",
        entity_id=batch.id,
        actor_from=transaction.commodity_code,
        actor_to=application.institution.name if application else "institution",
        payload={
            "batch_id": batch.batch_id,
            "asset_ref_hash": batch.asset_ref_hash,
            "mno_receipt_id": batch.mno_receipt_id,
            "purchase_order": batch.purchase_order_ref,
            "delivery_order": batch.delivery_order_ref,
            "supplier_invoice": batch.supplier_invoice_ref,
            "verified_at": verified_at.isoformat(),
            "transaction_id": transaction.id,
            "phase": transaction.phase,
        },
        asset_ref_no=batch.asset_ref_hash or batch.batch_id,
        verified_at=verified_at,
        mno_receipt_id=batch.mno_receipt_id,
        institution_id=transaction.institution_id,
        transaction_id=transaction.id,
        application_id=transaction.application_id,
    )


def _issue_trade_docs_and_mail(
    db: Session,
    *,
    application: FinancingApplication | None,
    transaction: CommodityTransaction,
    batch: AssetBatch,
    source_dealer_code: str | None = None,
) -> None:
    issue_trade_documents(
        batch,
        source_dealer_code=source_dealer_code,
        commodity_code=transaction.commodity_code,
    )
    if not application:
        return
    try:
        notify_trade_documents_ready(db, application, transaction, batch)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Could not email Kenya trade documents")


def _active_dealer_for_institution(
    db: Session,
    institution_id: str | None,
    *,
    min_float: float | None = None,
) -> AgentDealer | None:
    """Prefer dealers with enough float; fall through to any active dealer when min_float is unset."""
    q = (
        db.query(AgentDealer)
        .filter(AgentDealer.active.is_(True))
        .filter(
            (AgentDealer.institution_id == institution_id) | (AgentDealer.institution_id.is_(None))
        )
        .order_by(AgentDealer.created_at)
    )
    dealers = q.all()
    if min_float is not None:
        funded = [d for d in dealers if float(d.float_balance) >= min_float]
        if funded:
            return funded[0]
        return None
    return dealers[0] if dealers else None


def _is_agent_dealer_purchase(transaction: CommodityTransaction) -> bool:
    mode = (transaction.mode or "").lower()
    commodity = (transaction.commodity_code or "").upper()
    return mode == TransactionMode.AGENT_DEALER or commodity == CommodityType.FLOAT_MPESA_DEALER


def _kenya_transaction_modes() -> tuple[str, ...]:
    return (TransactionMode.MNO, TransactionMode.AGENT_DEALER)


def _resolve_kenya_purchase_path(
    db: Session,
    *,
    institution_id: str,
    commodity_code: str | None,
    mode: str | None,
    amount: float | None = None,
) -> tuple[str, str]:
    """Use the dealer pool when one is active with enough float; otherwise MNO.

    Explicit AGENT_DEALER still selects the dealer path (purchase will enforce float).
    Auto path falls back to MNO when no dealer can cover `amount`.
    """
    mode_l = (mode or "").strip().lower()
    commodity = (commodity_code or "").strip().upper()
    explicit_dealer = mode_l == TransactionMode.AGENT_DEALER or commodity == CommodityType.FLOAT_MPESA_DEALER
    explicit_mno = mode_l == TransactionMode.MNO or bool(commodity and commodity != CommodityType.FLOAT_MPESA_DEALER)
    if explicit_dealer:
        return TransactionMode.AGENT_DEALER, CommodityType.FLOAT_MPESA_DEALER
    if explicit_mno:
        return mode_l or TransactionMode.MNO, commodity or "AIRTIME_SAFARICOM"
    dealer = _active_dealer_for_institution(db, institution_id, min_float=amount)
    if dealer:
        return TransactionMode.AGENT_DEALER, CommodityType.FLOAT_MPESA_DEALER
    # Dealer exists but underfunded (or none): retail mobile must still proceed via MNO.
    if _active_dealer_for_institution(db, institution_id) is not None and amount is not None:
        return TransactionMode.MNO, "AIRTIME_SAFARICOM"
    if _active_dealer_for_institution(db, institution_id):
        return TransactionMode.AGENT_DEALER, CommodityType.FLOAT_MPESA_DEALER
    return TransactionMode.MNO, "AIRTIME_SAFARICOM"


def create_mno_transaction(
    db: Session,
    *,
    application_id: str,
    commodity_code: str | None = None,
    mode: str | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> CommodityTransaction:
    application = (
        db.query(FinancingApplication)
        .options(joinedload(FinancingApplication.offer))
        .filter(FinancingApplication.id == application_id)
        .first()
    )
    if not application:
        raise ValueError(f"Application {application_id} not found")
    if application.eligibility_passed is not True:
        raise ValueError("Eligibility check must pass before starting MNO transaction")

    mode, commodity_code = _resolve_kenya_purchase_path(
        db,
        institution_id=application.institution_id,
        commodity_code=commodity_code,
        mode=mode,
        amount=_financing_amount(application),
    )
    if mode == TransactionMode.AGENT_DEALER:
        commodity_code = CommodityType.FLOAT_MPESA_DEALER

    existing = (
        db.query(CommodityTransaction)
        .filter(
            CommodityTransaction.application_id == application_id,
            CommodityTransaction.mode.in_(_kenya_transaction_modes()),
        )
        .first()
    )
    if existing:
        raise ValueError("Kenya transaction already exists for this application")

    broker = select_broker_for_commodity(db, commodity_code)
    transaction = CommodityTransaction(
        application_id=application.id,
        institution_id=application.institution_id,
        commodity_code=commodity_code,
        mode=mode,
        status=TransactionStatus.CREATED,
        phase=TransactionPhase.PHASE_1_PURCHASE,
        mno_code=commodity_code,
        broker_id=broker.id if broker else None,
    )
    db.add(transaction)
    db.flush()

    for leg_num in (LegNumber.PURCHASE, LegNumber.TRANSFER, LegNumber.SALE):
        db.add(TransactionLeg(transaction_id=transaction.id, leg_number=leg_num, status=LegStatus.PENDING))
    db.flush()

    application.status = ApplicationStatus.IN_PROGRESS
    application.current_phase = TransactionPhase.PHASE_1_PURCHASE
    log_shariah_step(
        db,
        step_id=ShariahStepId.MURABAHA_PURCHASE,
        entity_type="commodity_transaction",
        entity_id=transaction.id,
        actor_from=application.institution.name,
        actor_to=application.customer_ref,
        payload={"commodity_code": commodity_code, "mode": mode, "broker_id": transaction.broker_id},
        institution_id=application.institution_id,
        transaction_id=transaction.id,
        application_id=application.id,
    )
    log_audit(
        db,
        entity_type="commodity_transaction",
        entity_id=transaction.id,
        actor=actor,
        action="mno.transaction.created",
        details=f"commodity={commodity_code}",
    )
    dispatch_webhook_event(
        db,
        institution_id=application.institution_id,
        event=WebhookEvent.TRANSACTION_CREATED,
        data={"transaction_id": transaction.id, "mode": mode, "commodity_code": commodity_code},
    )
    return transaction


def get_mno_transaction(db: Session, application_id: str) -> CommodityTransaction | None:
    return (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.legs).joinedload(TransactionLeg.asset_batch))
        .filter(
            CommodityTransaction.application_id == application_id,
            CommodityTransaction.mode.in_(_kenya_transaction_modes()),
        )
        .order_by(CommodityTransaction.created_at.desc())
        .first()
    )


def require_possession_before_murabaha_offer(db: Session, application_id: str) -> CommodityTransaction:
    """Murabaha offer (Phase 2) requires sealed Leg 1 + constructive possession (Phase 1)."""
    from tawarruq.services.shariah_state_machine import assert_possession_sealed

    transaction = get_mno_transaction(db, application_id)
    if not transaction:
        raise ValueError(
            "Complete MNO purchase and constructive possession before generating Murabaha offer"
        )
    purchase = _get_leg(transaction, LegNumber.PURCHASE)
    if purchase.status != LegStatus.CONFIRMED:
        raise ValueError("Purchase leg must be confirmed before Murabaha offer")
    assert_possession_sealed(db, transaction)
    return transaction


def _financing_amount(application: FinancingApplication) -> float:
    if application.offer:
        return float(application.offer.cost_price)
    return float(application.amount_requested)


def execute_mno_purchase_leg(
    db: Session,
    transaction_id: str,
    *,
    actor: AuditActor = AuditActor.AI_WORKER,
) -> CommodityTransaction:
    transaction = (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.legs))
        .filter(CommodityTransaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise ValueError("Transaction not found")

    if _is_agent_dealer_purchase(transaction):
        transaction.mode = TransactionMode.AGENT_DEALER
        if transaction.commodity_code != CommodityType.FLOAT_MPESA_DEALER:
            transaction.commodity_code = CommodityType.FLOAT_MPESA_DEALER
        return execute_agent_dealer_purchase_leg(db, transaction_id, actor=actor)

    application = db.get(FinancingApplication, transaction.application_id)
    customer = application.customer if application else None
    leg = _get_leg(transaction, LegNumber.PURCHASE)
    if leg.status == LegStatus.CONFIRMED:
        return transaction

    amount = _financing_amount(application) if application else 0.0
    profile = resolve_integration_profile(db, transaction.institution_id)
    backend = get_mno_backend(transaction.mode, profile)
    response = backend.purchase_airtime(
        MnoPurchaseRequest(
            transaction_id=transaction.id,
            leg_id=leg.id,
            mno_code=transaction.commodity_code,
            amount=amount,
            institution_code=transaction.institution.code,
            customer_phone=customer.phone if customer else "",
        )
    )

    if response.result == MnoPurchaseResult.FAILED:
        update_leg_from_execution(db, leg, status=LegStatus.FAILED, error_message=response.error_message, actor=actor)
        transaction.status = TransactionStatus.FAILED
        return transaction

    batch = AssetBatch(
        leg_id=leg.id,
        batch_id=response.batch_id or "",
        asset_ref_hash=response.asset_ref_hash or "",
        mno_code=transaction.commodity_code,
        mno_receipt_id=response.mno_receipt_id,
        possession_status=PossessionStatus.PENDING,
    )
    db.add(batch)
    db.flush()

    if response.result == MnoPurchaseResult.AWAITING_POSSESSION:
        leg.status = LegStatus.AWAITING_POSSESSION
        transaction.status = TransactionStatus.AWAITING_POSSESSION
    else:
        batch.possession_status = PossessionStatus.VERIFIED
        verified_at = datetime.now(UTC)
        batch.verified_at = verified_at
        _issue_trade_docs_and_mail(db, application=application, transaction=transaction, batch=batch)
        if not batch.mno_receipt_id:
            raise ValueError("MNO receipt ID required before confirming purchase leg")
        update_leg_from_execution(
            db,
            leg,
            status=LegStatus.CONFIRMED,
            external_ref=response.batch_id,
            certificate_number=response.mno_receipt_id,
            issuer=transaction.commodity_code,
            actor=actor,
        )
        _log_constructive_possession(
            db, batch=batch, transaction=transaction, application=application, verified_at=verified_at
        )
        advance_phase(db, transaction, TransactionPhase.PHASE_2_MURABAHA)
        dispatch_webhook_event(
            db,
            institution_id=transaction.institution_id,
            event=WebhookEvent.POSSESSION_VERIFIED,
            data={"transaction_id": transaction.id, "batch_id": batch.batch_id},
        )

    refresh_transaction_status(db, transaction)
    return transaction


def execute_agent_dealer_purchase_leg(
    db: Session,
    transaction_id: str,
    *,
    actor: AuditActor = AuditActor.SYSTEM,
) -> CommodityTransaction:
    """Agent Dealer path: deduct from dealer float pool and auto-confirm possession.
    Used when institution's kenya_mode is 'agent_dealer' instead of Safaricom/Airtel.
    """
    import hashlib
    import uuid as _uuid

    transaction = (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.legs))
        .filter(CommodityTransaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise ValueError("Transaction not found")

    application = db.get(FinancingApplication, transaction.application_id)
    leg = _get_leg(transaction, LegNumber.PURCHASE)
    if leg.status == LegStatus.CONFIRMED:
        return transaction

    amount = _financing_amount(application) if application else 0.0

    dealer = _active_dealer_for_institution(db, transaction.institution_id)
    if not dealer:
        raise ValueError(
            "No active Agent Dealer configured for this institution. "
            "Register a dealer. The dealer must add float from their own desk."
        )
    if float(dealer.float_balance) < amount:
        raise ValueError(
            f"Agent Dealer '{dealer.business_name}' has insufficient float "
            f"(balance KES {dealer.float_balance:.2f}, required KES {amount:.2f}). "
            "Please top up float before proceeding."
        )

    dealer.float_balance = float(dealer.float_balance) - amount
    db.add(
        AgentDealerFloatTopup(
            dealer_id=dealer.id,
            amount=-amount,
            reference=f"TXN-{transaction.id[:8]}",
            note=f"Kenya step 2 draw {transaction.id[:8]}",
            added_by="system",
        )
    )

    batch_id = f"DEALER-{dealer.code}-{_uuid.uuid4().hex[:10].upper()}"
    receipt_id = f"BURUUJ-KE-{datetime.now(UTC).strftime('%Y%m%d')}-{_uuid.uuid4().hex[:8].upper()}"
    asset_hash = hashlib.sha256(f"{batch_id}:{receipt_id}:{amount}".encode()).hexdigest()

    batch = AssetBatch(
        leg_id=leg.id,
        batch_id=batch_id,
        asset_ref_hash=asset_hash,
        mno_code=transaction.commodity_code,
        mno_receipt_id=receipt_id,
        source_dealer_code=dealer.code,
        possession_status=PossessionStatus.VERIFIED,
    )
    db.add(batch)
    db.flush()

    verified_at = datetime.now(UTC)
    batch.verified_at = verified_at
    _issue_trade_docs_and_mail(
        db,
        application=application,
        transaction=transaction,
        batch=batch,
        source_dealer_code=dealer.code,
    )

    update_leg_from_execution(
        db, leg,
        status=LegStatus.CONFIRMED,
        external_ref=batch_id,
        certificate_number=receipt_id,
        issuer=f"Buruuj Fintech Ltd (via {dealer.business_name})",
        actor=actor,
    )
    _log_constructive_possession(db, batch=batch, transaction=transaction, application=application, verified_at=verified_at)
    advance_phase(db, transaction, TransactionPhase.PHASE_2_MURABAHA)
    dispatch_webhook_event(
        db,
        institution_id=transaction.institution_id,
        event=WebhookEvent.POSSESSION_VERIFIED,
        data={"transaction_id": transaction.id, "batch_id": batch_id, "dealer_id": dealer.id, "dealer_name": dealer.business_name},
    )
    refresh_transaction_status(db, transaction)
    return transaction


def verify_possession(
    db: Session,
    transaction_id: str,
    *,
    batch_id: str | None = None,
    mno_receipt_id: str | None = None,
    actor: AuditActor = AuditActor.MNO,
) -> CommodityTransaction:
    transaction = (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.legs).joinedload(TransactionLeg.asset_batch))
        .filter(CommodityTransaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise ValueError("Transaction not found")

    leg = _get_leg(transaction, LegNumber.PURCHASE)
    batch = leg.asset_batch
    if not batch:
        raise ValueError("No asset batch on purchase leg")

    resolved_batch = batch_id or batch.batch_id
    resolved_receipt = mno_receipt_id or batch.mno_receipt_id or ""
    profile = resolve_integration_profile(db, transaction.institution_id)
    backend = get_mno_backend(transaction.mode, profile)
    result = backend.verify_possession(
        PossessionVerifyRequest(
            batch_id=resolved_batch,
            mno_receipt_id=resolved_receipt,
            mno_code=transaction.commodity_code,
        )
    )

    if not result.verified:
        batch.possession_status = PossessionStatus.REJECTED
        raise ValueError(result.error_message or "Possession verification failed")

    batch.possession_status = PossessionStatus.VERIFIED
    verified_at = datetime.now(UTC)
    batch.verified_at = verified_at
    if result.asset_ref_hash:
        batch.asset_ref_hash = result.asset_ref_hash
    batch.mno_receipt_id = resolved_receipt
    if not batch.mno_receipt_id:
        raise ValueError("MNO receipt ID required for constructive possession")
    application = db.get(FinancingApplication, transaction.application_id)
    _issue_trade_docs_and_mail(db, application=application, transaction=transaction, batch=batch)

    update_leg_from_execution(
        db,
        leg,
        status=LegStatus.CONFIRMED,
        external_ref=batch.batch_id,
        certificate_number=resolved_receipt,
        issuer=transaction.commodity_code,
        actor=actor,
    )
    _log_constructive_possession(
        db, batch=batch, transaction=transaction, application=application, verified_at=verified_at
    )
    advance_phase(db, transaction, TransactionPhase.PHASE_2_MURABAHA)
    dispatch_webhook_event(
        db,
        institution_id=transaction.institution_id,
        event=WebhookEvent.POSSESSION_VERIFIED,
        data={"transaction_id": transaction.id, "batch_id": batch.batch_id},
    )
    refresh_transaction_status(db, transaction)
    return transaction


def execute_transfer_leg(
    db: Session,
    transaction_id: str,
    *,
    actor: AuditActor = AuditActor.AI_WORKER,
) -> CommodityTransaction:
    transaction = validate_transfer_allowed(db, transaction_id)

    application = db.get(FinancingApplication, transaction.application_id)
    if not application or not application.murabaha_contract or not application.murabaha_contract.signed_at:
        raise ShariahStateViolation("Murabaha contract must be signed before ownership transfer")

    leg = _get_leg(transaction, LegNumber.TRANSFER)
    if leg.status == LegStatus.CONFIRMED:
        return transaction

    update_leg_from_execution(
        db,
        leg,
        status=LegStatus.CONFIRMED,
        external_ref=f"OWN-{transaction.id[:8]}",
        certificate_number=f"OTC-{datetime.now(UTC).strftime('%Y%m%d')}-{transaction.id[:8]}",
        issuer="OTC",
        actor=actor,
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.OWNERSHIP_TRANSFER,
        entity_type="transaction_leg",
        entity_id=leg.id,
        actor_from=application.institution.name,
        actor_to=application.customer_ref,
        payload={"transaction_id": transaction.id},
        institution_id=transaction.institution_id,
        transaction_id=transaction.id,
        application_id=application.id,
    )
    record_customer_sale(db, application.id, actor=actor)
    refresh_transaction_status(db, transaction)
    return transaction


def execute_liquidation_leg(
    db: Session,
    transaction_id: str,
    *,
    actor: AuditActor = AuditActor.BROKER,
) -> CommodityTransaction:
    transaction = validate_liquidation_allowed(db, transaction_id)

    application = db.get(FinancingApplication, transaction.application_id)
    if not application:
        raise ValueError("Application not found")

    if not application.customer_agency:
        raise ValueError(
            "Customer must appoint Wakala (liquidation agent) before third-party sale. "
            "POST /kenya/applications/{id}/wakala with consent_ref."
        )

    broker = select_broker_for_commodity(db, transaction.commodity_code)
    if not broker:
        raise ValueError("No third-party broker available for commodity")
    if not validate_no_inah(db, transaction, broker=broker, actor=actor):
        transaction.status = TransactionStatus.FAILED
        raise ValueError("No-Inah guardrail blocked liquidation — broker is not independent")

    leg = _get_leg(transaction, LegNumber.SALE)
    if leg.status == LegStatus.CONFIRMED:
        return transaction

    spot = Decimal(str(application.offer.cost_price)) * Decimal("0.98")

    purchase_leg = _get_leg(transaction, LegNumber.PURCHASE)
    batch = purchase_leg.asset_batch
    profile = resolve_integration_profile(db, transaction.institution_id)
    broker_client = get_broker_client(profile)
    broker_result = broker_client.execute_liquidation(
        BrokerLiquidationRequest(
            transaction_id=transaction.id,
            application_id=application.id,
            commodity_code=transaction.commodity_code,
            batch_id=batch.batch_id if batch else "",
            asset_ref_hash=batch.asset_ref_hash if batch else "",
            spot_amount=spot,
            broker_code=broker.code,
            institution_code=application.institution.code,
        )
    )
    if not broker_result.success:
        transaction.status = TransactionStatus.FAILED
        raise ValueError(broker_result.error_message or "Broker liquidation failed")

    order = LiquidationOrder(
        transaction_id=transaction.id,
        broker_id=broker.id,
        spot_amount=spot,
        no_inah_validated=True,
        counterparty_code=broker.code,
        executed_at=datetime.now(UTC),
    )
    db.add(order)
    transaction.broker_id = broker.id
    db.flush()

    update_leg_from_execution(
        db,
        leg,
        status=LegStatus.CONFIRMED,
        external_ref=broker_result.external_ref or f"LIQ-{broker.code}-{transaction.id[:8]}",
        certificate_number=broker_result.certificate_number
        or f"SALE-{broker.code}-{datetime.now(UTC).strftime('%Y%m%d')}",
        issuer=broker.code,
        actor=actor,
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.THIRD_PARTY_LIQUIDATION,
        entity_type="liquidation_order",
        entity_id=order.id,
        actor_from=application.customer_ref,
        actor_to=broker.name,
        payload={"spot_amount": str(spot), "broker_code": broker.code},
        asset_ref_no=order.counterparty_code,
        institution_id=transaction.institution_id,
        transaction_id=transaction.id,
        application_id=application.id,
    )
    advance_phase(db, transaction, TransactionPhase.PHASE_3_LIQUIDATION)
    refresh_transaction_status(db, transaction)
    dispatch_webhook_event(
        db,
        institution_id=transaction.institution_id,
        event=WebhookEvent.LIQUIDATION_COMPLETED,
        data={"transaction_id": transaction.id, "broker_id": broker.id, "spot_amount": str(spot)},
    )
    return transaction


def complete_kenya_disbursement(
    db: Session,
    *,
    application_id: str,
    transaction_id: str,
    actor: AuditActor = AuditActor.SYSTEM,
) -> dict:
    disbursement = create_disbursement(db, application_id=application_id, transaction_id=transaction_id, actor=actor)
    wallet = credit_wallet(db, disbursement, actor=actor)
    transaction = db.get(CommodityTransaction, transaction_id)
    if transaction:
        advance_phase(db, transaction, TransactionPhase.PHASE_4_REPAYMENT)
    installments = generate_repayment_schedule(db, application_id, actor=actor)
    return {
        "disbursement_id": disbursement.id,
        "wallet_disbursement_id": wallet.id,
        "external_txn_id": wallet.external_txn_id,
        "installment_count": len(installments),
    }


def prepare_murabaha_for_application(db: Session, application_id: str) -> None:
    application = db.get(FinancingApplication, application_id)
    if not application or not application.offer or not application.offer.accepted_at:
        raise ValueError("Murabaha offer must be generated and accepted before contract")
    require_possession_before_murabaha_offer(db, application_id)
    create_murabaha_contract(db, application_id)
    db.flush()
    db.refresh(application)
    sign_murabaha_contract(db, application_id)


def run_ordered_kenya_flow(db: Session, application_id: str) -> CommodityTransaction:
    """Canonical Kenya sequence: eligibility → purchase → possession → offer → accept → murabaha → legs → disburse."""
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise ValueError("Application not found")

    if application.eligibility_passed is not True:
        from tawarruq.services.eligibility_service import run_eligibility_check

        run_eligibility_check(db, application_id)
        db.flush()
        db.refresh(application)
        if not application.eligibility_passed:
            raise ValueError("Eligibility failed")

    txn = get_mno_transaction(db, application_id)
    if not txn:
        dealer = _active_dealer_for_institution(db, application.institution_id)
        if dealer:
            txn = create_mno_transaction(
                db,
                application_id=application_id,
                commodity_code=CommodityType.FLOAT_MPESA_DEALER,
                mode=TransactionMode.AGENT_DEALER,
            )
        else:
            txn = create_mno_transaction(db, application_id=application_id)

    execute_mno_purchase_leg(db, txn.id)
    db.flush()
    db.refresh(txn)

    purchase_leg = _get_leg(txn, LegNumber.PURCHASE)
    if purchase_leg.status == LegStatus.AWAITING_POSSESSION:
        verify_possession(db, txn.id)

    require_possession_before_murabaha_offer(db, application_id)

    if not application.offer:
        from tawarruq.services import application_service

        application_service.create_offer(db, application_id)
        db.flush()
        db.refresh(application)
    if not application.offer.accepted_at:
        from tawarruq.services import application_service

        application_service.accept_offer(db, application_id)
        db.flush()
        db.refresh(application)

    prepare_murabaha_for_application(db, application_id)
    execute_transfer_leg(db, txn.id)

    from tawarruq.services.business_flow_service import appoint_wakala_with_customer_consent

    appoint_wakala_with_customer_consent(
        db, application_id, consent_ref="run-full-flow-wakala", actor=AuditActor.SYSTEM
    )

    execute_liquidation_leg(db, txn.id)
    complete_kenya_disbursement(db, application_id=application_id, transaction_id=txn.id)
    return txn


def _get_leg(transaction: CommodityTransaction, leg_number: LegNumber) -> TransactionLeg:
    for leg in transaction.legs:
        if leg.leg_number == leg_number:
            return leg
    raise ValueError(f"Leg {leg_number} not found")
