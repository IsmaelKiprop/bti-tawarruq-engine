from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from tawarruq.enums import AuditActor, ShariahStepId, WalletProvider, WebhookEvent
from tawarruq.integrations.airtel.disbursement import get_airtel_money_client
from tawarruq.integrations.base import IntegrationError
from tawarruq.integrations.mpesa.daraja import get_daraja_client
from tawarruq.models.application import FinancingApplication
from tawarruq.models.customer import Customer
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.kenya_flow import WalletDisbursement
from tawarruq.services.audit_service import log_audit
from tawarruq.services.integration_config_service import resolve_integration_profile
from tawarruq.services.shariah_audit_service import log_shariah_step
from tawarruq.services.webhook_service import dispatch_webhook_event


def _mock_credit(
    db: Session,
    disbursement: Disbursement,
    application: FinancingApplication | None,
    *,
    resolved_provider: str,
    resolved_wallet: str,
    actor: AuditActor,
) -> WalletDisbursement:
    import uuid

    external_txn_id = f"{resolved_provider.upper()}-MOCK-{uuid.uuid4().hex[:16].upper()}"
    wallet = WalletDisbursement(
        disbursement_id=disbursement.id,
        provider=resolved_provider,
        wallet_number=resolved_wallet,
        amount=disbursement.amount,
        external_txn_id=external_txn_id,
        status="credited",
        credited_at=datetime.now(UTC),
    )
    db.add(wallet)
    db.flush()
    _log_wallet_success(db, disbursement, application, wallet, resolved_wallet, external_txn_id, actor)
    return wallet


def _log_wallet_success(
    db: Session,
    disbursement: Disbursement,
    application: FinancingApplication | None,
    wallet: WalletDisbursement,
    wallet_number: str,
    external_txn_id: str,
    actor: AuditActor,
) -> None:
    payload = {
        "disbursement_id": disbursement.id,
        "provider": wallet.provider,
        "wallet_number": wallet_number,
        "amount": str(disbursement.amount),
        "external_txn_id": external_txn_id,
    }
    log_shariah_step(
        db,
        step_id=ShariahStepId.WALLET_DISBURSEMENT,
        entity_type="disbursement",
        entity_id=disbursement.id,
        actor_from=application.institution.name if application else "institution",
        actor_to=wallet_number,
        payload=payload,
        asset_ref_no=external_txn_id,
    )
    log_audit(
        db,
        entity_type="wallet_disbursement",
        entity_id=wallet.id,
        actor=actor,
        action="wallet.credited",
        evidence_ref=external_txn_id,
        details=f"amount={disbursement.amount} provider={wallet.provider}",
    )
    if application:
        dispatch_webhook_event(
            db,
            institution_id=application.institution_id,
            event=WebhookEvent.WALLET_CREDITED,
            data={
                "disbursement_id": disbursement.id,
                "external_txn_id": external_txn_id,
                "amount": str(disbursement.amount),
            },
        )


def credit_wallet(
    db: Session,
    disbursement: Disbursement,
    *,
    provider: str | None = None,
    wallet_number: str | None = None,
    actor: AuditActor = AuditActor.SYSTEM,
) -> WalletDisbursement:
    if disbursement.wallet_disbursement:
        return disbursement.wallet_disbursement

    application = db.get(FinancingApplication, disbursement.application_id)
    customer = db.get(Customer, application.customer_id) if application and application.customer_id else None
    if not application:
        raise ValueError("Application not found for disbursement")

    profile = resolve_integration_profile(db, application.institution_id)
    resolved_provider = provider or (customer.wallet_provider if customer else WalletProvider.MPESA)
    resolved_wallet = wallet_number or (customer.wallet_number if customer else "")
    if not resolved_wallet:
        raise ValueError("Wallet number required for disbursement")

    use_live_mpesa = (
        profile.is_live and resolved_provider == WalletProvider.MPESA and profile.mpesa_configured
    )
    use_live_airtel = (
        profile.is_live
        and resolved_provider == WalletProvider.AIRTEL_MONEY
        and profile.airtel_money_configured
    )

    if not use_live_mpesa and not use_live_airtel:
        return _mock_credit(
            db, disbursement, application, resolved_provider=resolved_provider, resolved_wallet=resolved_wallet, actor=actor
        )

    if use_live_airtel:
        airtel = get_airtel_money_client(profile)
        try:
            result = airtel.disburse(
                phone=resolved_wallet,
                amount=Decimal(str(disbursement.amount)),
                reference=disbursement.id[:12],
                remarks=f"Tawarruq disbursement {disbursement.id[:8]}",
            )
        except IntegrationError as exc:
            raise ValueError(str(exc)) from exc
        external_ref = str(
            result.get("transaction_id") or result.get("reference") or result.get("txn_id") or disbursement.id[:12]
        )
        wallet = WalletDisbursement(
            disbursement_id=disbursement.id,
            provider=resolved_provider,
            wallet_number=resolved_wallet,
            amount=disbursement.amount,
            external_txn_id=external_ref,
            status="credited",
            credited_at=datetime.now(UTC),
        )
        db.add(wallet)
        db.flush()
        _log_wallet_success(db, disbursement, application, wallet, resolved_wallet, external_ref, actor)
        return wallet

    daraja = get_daraja_client(profile)
    try:
        result = daraja.b2c_payment(
            phone=resolved_wallet,
            amount=Decimal(str(disbursement.amount)),
            remarks=f"Tawarruq disbursement {disbursement.id[:8]}",
            occasion="TawarruqFinancing",
        )
    except IntegrationError as exc:
        raise ValueError(str(exc)) from exc

    external_ref = result.get("OriginatorConversationID") or result.get("ConversationID")
    wallet = WalletDisbursement(
        disbursement_id=disbursement.id,
        provider=resolved_provider,
        wallet_number=resolved_wallet,
        amount=disbursement.amount,
        external_txn_id=external_ref,
        status="pending",
    )
    db.add(wallet)
    db.flush()
    log_audit(
        db,
        entity_type="wallet_disbursement",
        entity_id=wallet.id,
        actor=actor,
        action="wallet.b2c_initiated",
        evidence_ref=external_ref,
        details=f"amount={disbursement.amount} awaiting Daraja callback",
    )
    return wallet


def complete_wallet_from_b2c_callback(
    db: Session,
    *,
    originator_conversation_id: str | None,
    conversation_id: str | None,
    result_code: int,
    result_desc: str,
    mpesa_receipt: str | None,
) -> WalletDisbursement | None:
    ref = originator_conversation_id or conversation_id
    if not ref:
        return None

    wallet = (
        db.query(WalletDisbursement)
        .filter(WalletDisbursement.external_txn_id == ref)
        .first()
    )
    if not wallet:
        wallet = (
            db.query(WalletDisbursement)
            .filter(WalletDisbursement.external_txn_id == conversation_id)
            .first()
        )
    if not wallet or wallet.status == "credited":
        return wallet

    disbursement = wallet.disbursement
    application = db.get(FinancingApplication, disbursement.application_id) if disbursement else None

    if result_code == 0:
        wallet.status = "credited"
        wallet.credited_at = datetime.now(UTC)
        if mpesa_receipt:
            wallet.external_txn_id = mpesa_receipt
        _log_wallet_success(
            db,
            disbursement,
            application,
            wallet,
            wallet.wallet_number,
            wallet.external_txn_id or ref,
            AuditActor.MNO,
        )
    else:
        wallet.status = "failed"
        log_audit(
            db,
            entity_type="wallet_disbursement",
            entity_id=wallet.id,
            actor=AuditActor.MNO,
            action="wallet.b2c_failed",
            details=result_desc,
        )
    db.flush()
    return wallet
