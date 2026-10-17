"""SACCO CBS execute path: stamp contracts, trade via Sedania, vault certs, webhook the SACCO.

Buruuj never disburses principal cash on this path. Mwalimu (or any SACCO CBS) pays the member.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.enums import (
    ApplicationStatus,
    AuditActor,
    ExecutionStatus,
    ShariahStepId,
    TransactionPhase,
    VaultCertificateKind,
    WebhookEvent,
)
from tawarruq.integrations.base import IntegrationError
from tawarruq.integrations.sedania.client import (
    SedaniaLiquidateRequest,
    SedaniaMurabahahRequest,
    SedaniaPurchaseRequest,
    get_sedania_client,
)
from tawarruq.models.application import FinancingApplication
from tawarruq.models.customer import Customer
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.execution import CertificateVault, TawarruqExecution
from tawarruq.models.institution import Institution
from tawarruq.models.integration import WebhookSubscription
from tawarruq.models.kenya_flow import WalletDisbursement
from tawarruq.schemas.sacco import (
    LegalStampRead,
    SaccoExecuteRead,
    SaccoExecuteRequest,
    VaultCertificateRead,
)
from tawarruq.services.audit_service import log_audit
from tawarruq.services.certificate_vault_service import store_certificate, vault_public_url
from tawarruq.services.legal_token_service import stamp_wad, stamp_wakalah
from tawarruq.services.shariah_audit_service import log_shariah_step
from tawarruq.services.webhook_service import deliver_signed_webhook, dispatch_webhook_event

logger = logging.getLogger(__name__)


def _money(value: Decimal | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def resolve_sacco_customer(db: Session, institution_id: str, customer_id: str) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer and customer.institution_id == institution_id:
        return customer
    matches = (
        db.query(Customer)
        .filter(
            Customer.institution_id == institution_id,
            or_(
                Customer.phone == customer_id,
                Customer.national_id == customer_id,
                Customer.wallet_number == customer_id,
            ),
        )
        .all()
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise HTTPException(status_code=400, detail="customer_id matched more than one borrower")
    raise HTTPException(
        status_code=404,
        detail="Pre-approved borrower not found. Onboard the member before calling /tawarruq/execute.",
    )


def _certificate_read(vault: CertificateVault) -> VaultCertificateRead:
    serials: list[str] = []
    if vault.serial_numbers_json:
        try:
            parsed = json.loads(vault.serial_numbers_json)
            if isinstance(parsed, list):
                serials = [str(item) for item in parsed]
        except json.JSONDecodeError:
            serials = []
    return VaultCertificateRead(
        kind=vault.kind,
        certificate_number=vault.certificate_number,
        source=vault.source,
        url=vault_public_url(vault),
        source_url=vault.source_url,
        batch_id=vault.batch_id,
        serial_numbers=serials,
        retention_until=vault.retention_until,
    )


def to_execute_read(db: Session, execution: TawarruqExecution) -> SaccoExecuteRead:
    vaults = (
        db.query(CertificateVault)
        .filter(CertificateVault.execution_id == execution.id)
        .order_by(CertificateVault.received_at.asc())
        .all()
    )
    certificates = {item.kind: _certificate_read(item) for item in vaults}
    wad = (
        LegalStampRead(token_id=execution.wad_token_id, signature=execution.wad_signature, kind="wad")
        if execution.wad_token_id and execution.wad_signature
        else None
    )
    wakalah = (
        LegalStampRead(
            token_id=execution.wakalah_token_id,
            signature=execution.wakalah_signature,
            kind="wakalah",
        )
        if execution.wakalah_token_id and execution.wakalah_signature
        else None
    )
    return SaccoExecuteRead(
        execution_id=execution.id,
        application_id=execution.application_id,
        customer_id=execution.customer_id,
        institution_id=execution.institution_id,
        amount=_money(execution.amount),
        profit_amount=_money(execution.profit_amount),
        deferred_price=_money(execution.deferred_price),
        tenor_months=execution.tenor_months,
        currency=execution.currency,
        status=execution.status,
        sedania_batch_id=execution.sedania_batch_id,
        wad=wad,
        wakalah=wakalah,
        certificates=certificates,
        callback_delivered=execution.callback_delivered_at is not None,
        cash_disbursement="sacco_cbs",
        error_message=execution.error_message,
        created_at=execution.created_at,
        completed_at=execution.completed_at,
    )


def _assert_no_bti_cash(db: Session, application_id: str | None) -> None:
    if not application_id:
        return
    wallet = (
        db.query(WalletDisbursement)
        .join(Disbursement, WalletDisbursement.disbursement_id == Disbursement.id)
        .filter(Disbursement.application_id == application_id)
        .first()
    )
    if wallet:
        raise HTTPException(
            status_code=500,
            detail="SACCO execute path must not create a Buruuj wallet disbursement",
        )


def _relay_certificates(db: Session, execution: TawarruqExecution, body: dict) -> bool:
    event_name = str(WebhookEvent.TAWARRUQ_CERTIFICATES_READY)
    payload = json.dumps({"event": event_name, "data": body}, default=str).encode()
    delivered = False

    dispatch_webhook_event(
        db,
        institution_id=execution.institution_id,
        event=WebhookEvent.TAWARRUQ_CERTIFICATES_READY,
        data=body,
    )
    subs = (
        db.query(WebhookSubscription)
        .filter(
            WebhookSubscription.institution_id == execution.institution_id,
            WebhookSubscription.active.is_(True),
        )
        .all()
    )
    if any(
        event_name in [e.strip() for e in sub.events.split(",")] or "*" in [e.strip() for e in sub.events.split(",")]
        for sub in subs
    ):
        delivered = True

    if execution.callback_url:
        secret = next((sub.secret for sub in subs), "sacco-callback")
        if deliver_signed_webhook(
            url=execution.callback_url,
            secret=secret,
            payload=payload,
            event_name=event_name,
        ):
            delivered = True
    return delivered


def execute_sacco_facility(
    db: Session,
    payload: SaccoExecuteRequest,
    *,
    institution: Institution,
) -> TawarruqExecution:
    if payload.client_request_id:
        existing = (
            db.query(TawarruqExecution)
            .filter(
                TawarruqExecution.institution_id == institution.id,
                TawarruqExecution.client_request_id == payload.client_request_id,
            )
            .first()
        )
        if existing:
            return existing

    customer = resolve_sacco_customer(db, institution.id, payload.customer_id)
    settings = get_settings()
    rate = payload.profit_rate if payload.profit_rate is not None else Decimal(str(settings.sedania_default_profit_rate))
    amount = _money(payload.amount)
    profit = _money(amount * rate)
    deferred = _money(amount + profit)

    application = FinancingApplication(
        institution_id=institution.id,
        customer_id=customer.id,
        customer_ref=customer.national_id or customer.phone,
        customer_name=customer.full_name,
        currency=payload.currency,
        amount_requested=amount,
        term_months=payload.tenor,
        purpose="sacco_sedania: inbound facility request",
        status=ApplicationStatus.IN_PROGRESS,
        eligibility_passed=None,
        current_phase=TransactionPhase.PHASE_1_PURCHASE,
        wad_text=None,
        wad_accepted_at=None,
    )
    db.add(application)
    db.flush()

    execution = TawarruqExecution(
        institution_id=institution.id,
        application_id=application.id,
        customer_id=customer.id,
        client_request_id=payload.client_request_id,
        amount=amount,
        profit_amount=profit,
        deferred_price=deferred,
        tenor_months=payload.tenor,
        currency=payload.currency,
        status=ExecutionStatus.RECEIVED,
        callback_url=payload.callback_url,
    )
    db.add(execution)
    db.flush()

    log_audit(
        db,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor=AuditActor.SACCO,
        action="tawarruq.execute.received",
        details=f"customer={customer.id} amount={amount} tenor={payload.tenor}",
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.FINANCING_REQUEST,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="sacco_cbs",
        actor_to="bti",
        payload={"amount": str(amount), "tenor": payload.tenor, "customer_id": customer.id},
        institution_id=institution.id,
        application_id=application.id,
    )

    try:
        execution.status = ExecutionStatus.STAMPING_CONTRACTS
        wad = stamp_wad(
            execution_id=execution.id,
            customer_id=customer.id,
            customer_name=customer.full_name,
            institution_name=institution.name,
            deferred_price=deferred,
            currency=payload.currency,
            tenor_months=payload.tenor,
        )
        wakalah = stamp_wakalah(
            execution_id=execution.id,
            customer_id=customer.id,
            customer_name=customer.full_name,
            institution_name=institution.name,
        )
        execution.wad_token_id = wad.token_id
        execution.wad_signature = wad.signature
        execution.wakalah_token_id = wakalah.token_id
        execution.wakalah_signature = wakalah.signature
        application.wad_text = wad.text
        application.wad_accepted_at = datetime.now(UTC)
        store_certificate(
            db,
            execution_id=execution.id,
            institution_id=institution.id,
            application_id=application.id,
            kind=VaultCertificateKind.WAD,
            certificate_number=wad.token_id,
            source="bti_token_engine",
            payload={**wad.payload, "signature": wad.signature},
        )
        store_certificate(
            db,
            execution_id=execution.id,
            institution_id=institution.id,
            application_id=application.id,
            kind=VaultCertificateKind.WAKALAH,
            certificate_number=wakalah.token_id,
            source="bti_token_engine",
            payload={**wakalah.payload, "signature": wakalah.signature},
        )
        log_shariah_step(
            db,
            step_id=ShariahStepId.WAD_UNDERTAKING,
            entity_type="tawarruq_execution",
            entity_id=execution.id,
            actor_from="bti",
            actor_to="customer",
            payload={"wad_token_id": wad.token_id},
            institution_id=institution.id,
            application_id=application.id,
        )
        log_shariah_step(
            db,
            step_id=ShariahStepId.WAKALA_APPOINTMENT,
            entity_type="tawarruq_execution",
            entity_id=execution.id,
            actor_from="customer",
            actor_to="bti",
            payload={"wakalah_token_id": wakalah.token_id},
            institution_id=institution.id,
            application_id=application.id,
        )

        client = get_sedania_client()
        execution.status = ExecutionStatus.SPOT_PURCHASE
        purchase = client.purchase(
            SedaniaPurchaseRequest(
                execution_id=execution.id,
                institution_code=institution.code,
                customer_id=customer.id,
                amount=amount,
                currency=payload.currency,
            )
        )
        if not purchase.success or not purchase.batch_id or not purchase.certificate_number:
            raise IntegrationError(purchase.error_message or "Sedania purchase did not return a batch")
        execution.sedania_batch_id = purchase.batch_id
        store_certificate(
            db,
            execution_id=execution.id,
            institution_id=institution.id,
            application_id=application.id,
            kind=VaultCertificateKind.PURCHASE,
            certificate_number=purchase.certificate_number,
            source="sedania",
            payload=purchase.payload,
            source_url=purchase.certificate_url,
            serial_numbers=purchase.serial_numbers,
            batch_id=purchase.batch_id,
        )
        log_shariah_step(
            db,
            step_id=ShariahStepId.CONSTRUCTIVE_POSSESSION,
            entity_type="tawarruq_execution",
            entity_id=execution.id,
            actor_from="sedania",
            actor_to="sacco",
            payload={
                "batch_id": purchase.batch_id,
                "serial_numbers": purchase.serial_numbers,
                "certificate_number": purchase.certificate_number,
            },
            asset_ref_no=purchase.batch_id,
            institution_id=institution.id,
            application_id=application.id,
        )

        execution.status = ExecutionStatus.DEFERRED_MURABAHAH
        murabahah = client.transfer_murabahah(
            SedaniaMurabahahRequest(
                execution_id=execution.id,
                batch_id=purchase.batch_id,
                cost_price=amount,
                profit_amount=profit,
                deferred_price=deferred,
                currency=payload.currency,
                customer_id=customer.id,
                tenor_months=payload.tenor,
            )
        )
        if not murabahah.success or not murabahah.certificate_number:
            raise IntegrationError(murabahah.error_message or "Sedania Murabahah transfer failed")
        store_certificate(
            db,
            execution_id=execution.id,
            institution_id=institution.id,
            application_id=application.id,
            kind=VaultCertificateKind.MURABAHAH,
            certificate_number=murabahah.certificate_number,
            source="sedania",
            payload=murabahah.payload,
            source_url=murabahah.certificate_url,
            batch_id=purchase.batch_id,
        )
        log_shariah_step(
            db,
            step_id=ShariahStepId.OWNERSHIP_TRANSFER,
            entity_type="tawarruq_execution",
            entity_id=execution.id,
            actor_from="sacco",
            actor_to="customer",
            payload={
                "cost_price": str(amount),
                "profit_amount": str(profit),
                "deferred_price": str(deferred),
                "certificate_number": murabahah.certificate_number,
            },
            asset_ref_no=purchase.batch_id,
            institution_id=institution.id,
            application_id=application.id,
        )

        execution.status = ExecutionStatus.SPOT_LIQUIDATION
        liquidation = client.liquidate(
            SedaniaLiquidateRequest(
                execution_id=execution.id,
                batch_id=purchase.batch_id,
                spot_amount=amount,
                currency=payload.currency,
                wakeel_ref=wakalah.token_id,
            )
        )
        if not liquidation.success or not liquidation.certificate_number:
            raise IntegrationError(liquidation.error_message or "Sedania liquidation failed")
        store_certificate(
            db,
            execution_id=execution.id,
            institution_id=institution.id,
            application_id=application.id,
            kind=VaultCertificateKind.LIQUIDATION,
            certificate_number=liquidation.certificate_number,
            source="sedania",
            payload=liquidation.payload,
            source_url=liquidation.certificate_url,
            batch_id=purchase.batch_id,
        )
        log_shariah_step(
            db,
            step_id=ShariahStepId.THIRD_PARTY_LIQUIDATION,
            entity_type="tawarruq_execution",
            entity_id=execution.id,
            actor_from="bti",
            actor_to="sedania",
            payload={"certificate_number": liquidation.certificate_number, "independent_buyer": True},
            asset_ref_no=purchase.batch_id,
            institution_id=institution.id,
            application_id=application.id,
        )

        _assert_no_bti_cash(db, application.id)

        execution.status = ExecutionStatus.WEBHOOK_RELAY
        db.flush()
        read = to_execute_read(db, execution)
        callback_body = {
            "execution_id": execution.id,
            "application_id": application.id,
            "customer_id": customer.id,
            "amount": str(amount),
            "currency": payload.currency,
            "status": ExecutionStatus.READY_FOR_SACCO_DISBURSEMENT,
            "cash_disbursement": "sacco_cbs",
            "certificates": {
                "purchase": read.certificates.get("purchase").url if read.certificates.get("purchase") else None,
                "murabahah": read.certificates.get("murabahah").url if read.certificates.get("murabahah") else None,
                "liquidation": read.certificates.get("liquidation").url if read.certificates.get("liquidation") else None,
            },
            "certificate_urls": [
                read.certificates["purchase"].url if read.certificates.get("purchase") else None,
                read.certificates["murabahah"].url if read.certificates.get("murabahah") else None,
                read.certificates["liquidation"].url if read.certificates.get("liquidation") else None,
            ],
        }
        if _relay_certificates(db, execution, callback_body):
            execution.callback_delivered_at = datetime.now(UTC)

        execution.status = ExecutionStatus.READY_FOR_SACCO_DISBURSEMENT
        execution.completed_at = datetime.now(UTC)
        application.status = ApplicationStatus.COMPLETED
        application.current_phase = TransactionPhase.COMPLETED
        log_audit(
            db,
            entity_type="tawarruq_execution",
            entity_id=execution.id,
            actor=AuditActor.SYSTEM,
            action="tawarruq.execute.ready_for_sacco_disbursement",
            details="Certificates vaulted. Principal cash remains with the SACCO CBS.",
        )
        db.flush()
        return execution
    except (IntegrationError, HTTPException, ValueError) as exc:
        logger.exception("SACCO execute failed execution_id=%s", execution.id)
        execution.status = ExecutionStatus.FAILED
        execution.error_message = str(getattr(exc, "detail", None) or exc)
        application.status = ApplicationStatus.FAILED
        db.flush()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=502, detail=execution.error_message) from exc
