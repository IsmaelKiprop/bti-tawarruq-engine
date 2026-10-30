"""Bank Commodity Murabahah financing through AS SIDQ (Sedania deck, 20 Oct 2026).

Approved flow: SASC as independent wakeel, muqassah, bank credits CASA.
AAOIFI flow: SASC as Rasul (messenger), no muqassah, bank credits CASA.
Physical delivery: customer keeps the commodity (qabd hakiki) after full settlement.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from tawarruq.enums import (
    ApplicationStatus,
    AuditActor,
    ExecutionPath,
    ExecutionStatus,
    PhysicalDeliveryStatus,
    SedaniaAgencyRole,
    SedaniaDeliveryMode,
    SedaniaFlowVariant,
    ShariahStepId,
    TransactionPhase,
    VaultCertificateKind,
    WebhookEvent,
)
from tawarruq.integrations.base import IntegrationError
from tawarruq.integrations.sedania.client import (
    SedaniaLiquidateRequest,
    SedaniaMurabahahRequest,
    SedaniaPhysicalDeliveryRequest,
    SedaniaPurchaseRequest,
    get_sedania_client,
)
from tawarruq.models.application import FinancingApplication
from tawarruq.models.customer import Customer
from tawarruq.models.execution import CertificateVault, TawarruqExecution
from tawarruq.models.institution import Institution
from tawarruq.schemas.sacco import LegalStampRead, SaccoExecuteRead, VaultCertificateRead
from tawarruq.schemas.sedania import (
    SedaniaDocumentIndex,
    SedaniaFinancingRead,
    SedaniaFinancingRequest,
    SedaniaStepRead,
)
from tawarruq.services.audit_service import log_audit
from tawarruq.services.certificate_vault_service import store_certificate, vault_public_url
from tawarruq.services.legal_token_service import (
    SASC_PARTY_CODE,
    stamp_cmp,
    stamp_wad,
    stamp_wakalah,
)
from tawarruq.services.sedania_document_service import (
    TRADE_DOC_LABELS,
    normalize_sedania_doc_kind,
    render_sedania_document,
    trade_pack_refs,
)
from tawarruq.services.shariah_audit_service import log_shariah_step
from tawarruq.services.webhook_service import dispatch_webhook_event

logger = logging.getLogger(__name__)

SUPPLIER_REF = "TELECOMMUNICATION_AIRTIME_AGGREGATOR"
DEFAULT_PURCHASER = "SEDANIA_RANDOM_PURCHASER"


def _money(value: Decimal | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


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


def _vault_map(db: Session, execution_id: str) -> dict[str, CertificateVault]:
    rows = (
        db.query(CertificateVault)
        .filter(CertificateVault.execution_id == execution_id)
        .order_by(CertificateVault.received_at.asc())
        .all()
    )
    return {item.kind: item for item in rows}


def _step_status(done: bool, skipped: bool = False) -> str:
    if skipped:
        return "skipped"
    return "done" if done else "pending"


def build_steps(execution: TawarruqExecution) -> list[SedaniaStepRead]:
    physical = execution.delivery_mode == SedaniaDeliveryMode.PHYSICAL
    rasul = execution.agency_role == SedaniaAgencyRole.RASUL
    approved = execution.flow_variant == SedaniaFlowVariant.APPROVED_WAKEEL and not physical
    agency_title = (
        "Appoint SASC as Rasul"
        if rasul
        else "Appoint SASC as wakeel"
    )
    steps = [
        SedaniaStepRead(
            n=1,
            id="cmp",
            title="Apply, sign financing contract, enter CMP",
            status=_step_status(bool(execution.wad_token_id)),
            detail="Customer signs the financing contract and enters the Commodity Murabahah Program.",
            documents=["cmp", "wad"],
        ),
        SedaniaStepRead(
            n=2,
            id="agency",
            title=agency_title,
            status=_step_status(bool(execution.wakalah_token_id), skipped=not execution.appoint_sasc),
            detail=(
                "Customer may appoint SEDANIA As Salam Capital independently as Rasul (messenger)."
                if rasul
                else "Customer may appoint SEDANIA As Salam Capital independently as wakeel (agent)."
            ),
            documents=["rasul" if rasul else "wakalah"],
        ),
        SedaniaStepRead(
            n=3,
            id="purchase",
            title="Bank purchases airtime on AS SIDQ",
            status=_step_status(bool(execution.sedania_batch_id and execution.purchase_order_ref)),
            detail="Institution buys telecommunication airtime on a spot and credit basis from the supplier via AS SIDQ.",
            documents=["purchase_order", "commodity_invoice", "purchase"],
        ),
        SedaniaStepRead(
            n=4,
            id="possession",
            title="Qabd hukmi (constructive possession)",
            status=_step_status(bool(execution.delivery_order_ref)),
            detail="Supplier delivers via AS SIDQ. The institution obtains constructive possession before any sale to the customer.",
            documents=["delivery_order"],
        ),
        SedaniaStepRead(
            n=5,
            id="murabahah",
            title="Murabahah deferred sale to the customer",
            status=_step_status(bool(execution.trading_ecert_ref)),
            detail="Institution sells the commodity at cost plus profit on deferred terms.",
            documents=["trading_ecert", "murabahah"],
        ),
    ]
    if physical:
        steps.extend(
            [
                SedaniaStepRead(
                    n=6,
                    id="settlement",
                    title="Await full settlement for physical delivery",
                    status=_step_status(bool(execution.repayment_settled_at)),
                    detail="Customer opted to keep the commodity. Physical delivery waits until the deferred price is fully settled.",
                    documents=[],
                ),
                SedaniaStepRead(
                    n=7,
                    id="physical",
                    title="SASC arranges qabd hakiki",
                    status=_step_status(
                        execution.physical_delivery_status
                        in {PhysicalDeliveryStatus.ARRANGED, PhysicalDeliveryStatus.DELIVERED}
                    ),
                    detail="SEDANIA As Salam Capital arranges physical delivery with the commodity supplier.",
                    documents=["physical_delivery"],
                ),
            ]
        )
        return steps

    steps.append(
        SedaniaStepRead(
            n=6,
            id="liquidate",
            title="SASC sells to random purchasers on AS SIDQ",
            status=_step_status(bool(execution.purchaser_ref) and execution.status not in {
                ExecutionStatus.SPOT_PURCHASE,
                ExecutionStatus.DEFERRED_MURABAHAH,
                ExecutionStatus.STAMPING_CONTRACTS,
                ExecutionStatus.RECEIVED,
            }),
            detail=(
                "SASC acts as Rasul to convey the spot sale to random commodity purchasers."
                if rasul
                else "SASC acts as wakeel and sells the commodity on a spot and random basis."
            ),
            documents=["liquidation"],
        )
    )
    n = 7
    if approved:
        steps.append(
            SedaniaStepRead(
                n=n,
                id="muqassah",
                title="Muqassah (set-off)",
                status=_step_status(bool(execution.muqassah_ref)),
                detail="Purchaser authorizes the bank to pay the customer, then agrees to pay the seller for set-off.",
                documents=["muqassah"],
            )
        )
        n += 1
    if execution.path == ExecutionPath.BANK_FINANCING:
        steps.append(
            SedaniaStepRead(
                n=n,
                id="casa",
                title="Bank credits customer CASA",
                status=_step_status(bool(execution.casa_credited_at)),
                detail="The institution credits the Current or Savings Account after the independent sale.",
                documents=["casa_advice"],
            )
        )
    else:
        steps.append(
            SedaniaStepRead(
                n=n,
                id="sacco_payout",
                title="Relay certificates for SACCO payout",
                status=_step_status(execution.status == ExecutionStatus.READY_FOR_SACCO_DISBURSEMENT),
                detail="Buruuj relays the vault URLs. The SACCO CBS credits the member. Buruuj does not handle principal cash.",
                documents=[],
            )
        )
    return steps


def to_financing_read(db: Session, execution: TawarruqExecution) -> SedaniaFinancingRead:
    vaults = _vault_map(db, execution.id)
    certificates = {kind: _certificate_read(item) for kind, item in vaults.items()}
    wad = (
        LegalStampRead(token_id=execution.wad_token_id, signature=execution.wad_signature, kind="wad")
        if execution.wad_token_id and execution.wad_signature
        else None
    )
    agency_kind = "rasul" if execution.agency_role == SedaniaAgencyRole.RASUL else "wakalah"
    wakalah = (
        LegalStampRead(
            token_id=execution.wakalah_token_id,
            signature=execution.wakalah_signature,
            kind=agency_kind,
        )
        if execution.wakalah_token_id and execution.wakalah_signature
        else None
    )
    cmp_vault = vaults.get(VaultCertificateKind.CMP)
    cmp = (
        LegalStampRead(token_id=cmp_vault.certificate_number, signature="vaulted", kind="cmp")
        if cmp_vault
        else None
    )
    return SedaniaFinancingRead(
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
        cash_disbursement=execution.cash_disbursement,
        error_message=execution.error_message,
        created_at=execution.created_at,
        completed_at=execution.completed_at,
        path=execution.path,
        flow_variant=execution.flow_variant,
        delivery_mode=execution.delivery_mode,
        agency_role=execution.agency_role,
        agency_party=execution.agency_party,
        appoint_sasc=bool(execution.appoint_sasc),
        purchase_order_ref=execution.purchase_order_ref,
        commodity_invoice_ref=execution.commodity_invoice_ref,
        delivery_order_ref=execution.delivery_order_ref,
        trading_ecert_ref=execution.trading_ecert_ref,
        supplier_ref=execution.supplier_ref,
        purchaser_ref=execution.purchaser_ref,
        muqassah_ref=execution.muqassah_ref,
        muqassah_at=execution.muqassah_at,
        casa_account=execution.casa_account,
        casa_ref=execution.casa_ref,
        casa_credited_at=execution.casa_credited_at,
        physical_delivery_requested=bool(execution.physical_delivery_requested),
        physical_delivery_status=execution.physical_delivery_status,
        physical_delivery_notified_at=execution.physical_delivery_notified_at,
        repayment_settled_at=execution.repayment_settled_at,
        cmp=cmp,
        steps=build_steps(execution),
    )


def to_execute_read(db: Session, execution: TawarruqExecution) -> SaccoExecuteRead:
    """Backward-compatible SACCO envelope plus the new financing fields."""
    return to_financing_read(db, execution)


def store_trade_pack(
    db: Session,
    execution: TawarruqExecution,
    *,
    institution: Institution,
    customer: Customer,
) -> dict[str, str]:
    refs = trade_pack_refs(execution.id)
    execution.purchase_order_ref = refs["purchase_order"]
    execution.commodity_invoice_ref = refs["commodity_invoice"]
    execution.delivery_order_ref = refs["delivery_order"]
    execution.trading_ecert_ref = refs["trading_ecert"]
    execution.supplier_ref = execution.supplier_ref or SUPPLIER_REF
    issued = datetime.now(UTC).isoformat()
    common = {
        "institution_name": institution.name,
        "customer_name": customer.full_name,
        "amount": str(execution.amount),
        "currency": execution.currency,
        "issued_at": issued,
        "possession": "qabd hukmi",
        "platform": "AS SIDQ Digital Commodity Trading Platform",
    }
    docs = (
        (VaultCertificateKind.PURCHASE_ORDER, refs["purchase_order"], "Purchase Order"),
        (VaultCertificateKind.COMMODITY_INVOICE, refs["commodity_invoice"], "Commodity Invoice"),
        (VaultCertificateKind.DELIVERY_ORDER, refs["delivery_order"], "Delivery Order"),
        (VaultCertificateKind.TRADING_ECERT, refs["trading_ecert"], "Trading e-Cert"),
    )
    existing = {item.kind for item in execution.certificates} if execution.certificates else set()
    for kind, ref, title in docs:
        if kind in existing:
            continue
        store_certificate(
            db,
            execution_id=execution.id,
            institution_id=institution.id,
            application_id=execution.application_id,
            kind=kind,
            certificate_number=ref,
            source="as_sidq",
            payload={**common, "title": title, "ref": ref},
            batch_id=execution.sedania_batch_id,
        )
    return refs


def _existing_for_client(db: Session, institution_id: str, client_request_id: str | None) -> TawarruqExecution | None:
    if not client_request_id:
        return None
    return (
        db.query(TawarruqExecution)
        .filter(
            TawarruqExecution.institution_id == institution_id,
            TawarruqExecution.client_request_id == client_request_id,
        )
        .first()
    )


def execute_bank_financing(
    db: Session,
    payload: SedaniaFinancingRequest,
    *,
    institution: Institution,
) -> TawarruqExecution:
    existing = _existing_for_client(db, institution.id, payload.client_request_id)
    if existing:
        return existing

    from tawarruq.services.sacco_execute_service import resolve_sacco_customer

    customer = resolve_sacco_customer(db, institution.id, payload.customer_id)
    from tawarruq.services.platform_settings_service import sedania_profit_rate

    rate = payload.profit_rate if payload.profit_rate is not None else sedania_profit_rate(db)
    amount = _money(payload.amount)
    profit = _money(amount * rate)
    deferred = _money(amount + profit)
    agency_role = (
        SedaniaAgencyRole.RASUL
        if payload.flow_variant == SedaniaFlowVariant.AAOIFI_RASUL
        else SedaniaAgencyRole.WAKEEL
    )
    physical = payload.delivery_mode == SedaniaDeliveryMode.PHYSICAL
    casa_account = payload.casa_account or customer.wallet_number
    cash = "withheld_physical" if physical else "bank_casa"

    application = FinancingApplication(
        institution_id=institution.id,
        customer_id=customer.id,
        customer_ref=customer.national_id or customer.phone,
        customer_name=customer.full_name,
        currency=payload.currency,
        amount_requested=amount,
        term_months=payload.tenor,
        purpose=f"sedania_cmp:{payload.flow_variant}:{payload.delivery_mode}",
        status=ApplicationStatus.IN_PROGRESS,
        eligibility_passed=True,
        current_phase=TransactionPhase.PHASE_1_PURCHASE,
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
        path=ExecutionPath.BANK_FINANCING,
        flow_variant=payload.flow_variant,
        delivery_mode=payload.delivery_mode,
        agency_role=agency_role,
        agency_party=SASC_PARTY_CODE,
        appoint_sasc=payload.appoint_sasc,
        casa_account=casa_account,
        cash_disbursement=cash,
        physical_delivery_requested=physical,
        physical_delivery_status=(
            PhysicalDeliveryStatus.REQUESTED if physical else PhysicalDeliveryStatus.NOT_APPLICABLE
        ),
        callback_url=payload.callback_url,
        supplier_ref=SUPPLIER_REF,
    )
    db.add(execution)
    db.flush()

    log_audit(
        db,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor=AuditActor.HUMAN,
        action="sedania.financing.received",
        details=f"variant={payload.flow_variant} delivery={payload.delivery_mode} amount={amount}",
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.FINANCING_REQUEST,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="customer",
        actor_to="bank",
        payload={"amount": str(amount), "currency": payload.currency, "flow_variant": str(payload.flow_variant)},
        institution_id=institution.id,
        application_id=application.id,
    )
    try:
        from tawarruq.services.customer_notify_service import notify_step_ready

        notify_step_ready(
            db,
            email=customer.email,
            customer_name=customer.full_name,
            customer_ref=application.customer_ref,
            title="Sedania financing started",
            body_line="Your Sedania facility has been created. Open your journey to follow the trade documents.",
            institution_name=institution.name,
        )
    except Exception:
        pass

    try:
        _stamp_cmp_and_agency(db, execution, institution, customer, amount)
        _run_as_sidq_legs(db, execution, institution, customer, amount, profit, deferred)
        if physical:
            execution.status = ExecutionStatus.AWAITING_SETTLEMENT
            execution.physical_delivery_status = PhysicalDeliveryStatus.AWAITING_SETTLEMENT
            application.current_phase = TransactionPhase.PHASE_4_REPAYMENT
            log_audit(
                db,
                entity_type="tawarruq_execution",
                entity_id=execution.id,
                actor=AuditActor.SYSTEM,
                action="sedania.financing.awaiting_settlement",
                details="Customer opted to keep the commodity. Physical delivery waits for full settlement.",
            )
            db.flush()
            return execution

        _liquidate_via_sasc(db, execution, institution, customer, amount)
        if payload.flow_variant == SedaniaFlowVariant.APPROVED_WAKEEL:
            _record_muqassah(db, execution, institution, customer, amount)
        _credit_casa(db, execution, institution, customer, amount)

        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.now(UTC)
        application.status = ApplicationStatus.COMPLETED
        application.current_phase = TransactionPhase.COMPLETED
        dispatch_webhook_event(
            db,
            institution_id=institution.id,
            event=WebhookEvent.SEDANIA_FINANCING_COMPLETED,
            data={"execution_id": execution.id, "status": execution.status, "casa_ref": execution.casa_ref},
        )
        log_audit(
            db,
            entity_type="tawarruq_execution",
            entity_id=execution.id,
            actor=AuditActor.SYSTEM,
            action="sedania.financing.completed",
            details=f"CASA {execution.casa_account} credited {amount} {execution.currency}",
        )
        db.flush()
        try:
            from tawarruq.services.customer_notify_service import notify_step_ready

            notify_step_ready(
                db,
                email=customer.email,
                customer_name=customer.full_name,
                customer_ref=application.customer_ref,
                title="Sedania documents ready",
                body_line="Trade documents are ready on your customer journey.",
                institution_name=institution.name,
            )
        except Exception:
            pass
        return execution
    except (IntegrationError, HTTPException, ValueError) as exc:
        logger.exception("Sedania financing failed execution_id=%s", execution.id)
        execution.status = ExecutionStatus.FAILED
        execution.error_message = str(getattr(exc, "detail", None) or exc)
        application.status = ApplicationStatus.FAILED
        db.flush()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=502, detail=execution.error_message) from exc


def mark_repayment_settled(db: Session, execution: TawarruqExecution) -> TawarruqExecution:
    if execution.repayment_settled_at:
        return execution
    execution.repayment_settled_at = datetime.now(UTC)
    log_audit(
        db,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor=AuditActor.HUMAN,
        action="sedania.financing.settled",
        details="Deferred Murabahah price marked fully settled.",
    )
    db.flush()
    return execution


def arrange_physical_delivery(db: Session, execution: TawarruqExecution) -> TawarruqExecution:
    if execution.delivery_mode != SedaniaDeliveryMode.PHYSICAL:
        raise HTTPException(status_code=400, detail="This facility did not opt for physical delivery.")
    if not execution.repayment_settled_at:
        raise HTTPException(
            status_code=409,
            detail="Physical delivery is arranged only after the deferred Murabahah price is fully settled.",
        )
    if execution.physical_delivery_status in {
        PhysicalDeliveryStatus.ARRANGED,
        PhysicalDeliveryStatus.DELIVERED,
    }:
        return execution
    if not execution.sedania_batch_id:
        raise HTTPException(status_code=409, detail="No AS SIDQ batch is available to deliver.")

    institution = execution.institution
    customer = execution.customer
    client = get_sedania_client()
    result = client.arrange_physical_delivery(
        SedaniaPhysicalDeliveryRequest(
            execution_id=execution.id,
            batch_id=execution.sedania_batch_id,
            customer_id=execution.customer_id,
            amount=_money(execution.amount),
            currency=execution.currency,
            supplier_ref=execution.supplier_ref or SUPPLIER_REF,
        )
    )
    if not result.success:
        raise HTTPException(status_code=502, detail=result.error_message or "Physical delivery arrangement failed")

    refs = trade_pack_refs(execution.id)
    execution.status = ExecutionStatus.PHYSICAL_DELIVERY
    execution.physical_delivery_status = PhysicalDeliveryStatus.ARRANGED
    execution.physical_delivery_notified_at = datetime.now(UTC)
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=execution.institution_id,
        application_id=execution.application_id,
        kind=VaultCertificateKind.PHYSICAL_DELIVERY,
        certificate_number=result.certificate_number or refs["physical"],
        source="sedania",
        payload={
            **result.payload,
            "title": "Physical delivery (qabd hakiki)",
            "ref": result.certificate_number or refs["physical"],
            "institution_name": institution.name if institution else None,
            "customer_name": customer.full_name if customer else None,
        },
        source_url=result.certificate_url,
        batch_id=execution.sedania_batch_id,
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.PHYSICAL_DELIVERY,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="sedania",
        actor_to="customer",
        payload={"certificate_number": result.certificate_number, "qabd_hakiki": True},
        asset_ref_no=execution.sedania_batch_id,
        institution_id=execution.institution_id,
        application_id=execution.application_id,
    )
    dispatch_webhook_event(
        db,
        institution_id=execution.institution_id,
        event=WebhookEvent.PHYSICAL_DELIVERY_ARRANGED,
        data={"execution_id": execution.id, "batch_id": execution.sedania_batch_id},
    )
    execution.status = ExecutionStatus.COMPLETED
    execution.completed_at = datetime.now(UTC)
    if execution.application:
        execution.application.status = ApplicationStatus.COMPLETED
        execution.application.current_phase = TransactionPhase.COMPLETED
    db.flush()
    return execution


def list_document_index(db: Session, execution: TawarruqExecution) -> list[SedaniaDocumentIndex]:
    vaults = _vault_map(db, execution.id)
    rows: list[SedaniaDocumentIndex] = []
    for kind, label in TRADE_DOC_LABELS.items():
        vault = vaults.get(kind)
        rows.append(
            SedaniaDocumentIndex(
                kind=kind,
                label=label,
                available=vault is not None,
                ref=vault.certificate_number if vault else None,
                url=vault_public_url(vault) if vault else None,
            )
        )
    return rows


def render_execution_document(db: Session, execution: TawarruqExecution, kind: str) -> tuple[str, str]:
    resolved = normalize_sedania_doc_kind(kind)
    vaults = _vault_map(db, execution.id)
    vault = vaults.get(resolved)
    payload: dict[str, Any] = {}
    if vault:
        try:
            payload = json.loads(vault.payload_json)
        except json.JSONDecodeError:
            payload = {}
        if execution.institution and "institution_name" not in payload:
            payload["institution_name"] = execution.institution.name
        if execution.customer and "customer_name" not in payload:
            payload["customer_name"] = execution.customer.full_name
    html = render_sedania_document(execution, resolved, payload)
    ref = (vault.certificate_number if vault else resolved).replace(" ", "-")
    return html, f"{ref}.html"


def _stamp_cmp_and_agency(
    db: Session,
    execution: TawarruqExecution,
    institution: Institution,
    customer: Customer,
    amount: Decimal,
) -> None:
    execution.status = ExecutionStatus.STAMPING_CONTRACTS
    cmp = stamp_cmp(
        execution_id=execution.id,
        customer_id=customer.id,
        customer_name=customer.full_name,
        institution_name=institution.name,
        amount=amount,
        currency=execution.currency,
        agency_role=execution.agency_role,
    )
    wad = stamp_wad(
        execution_id=execution.id,
        customer_id=customer.id,
        customer_name=customer.full_name,
        institution_name=institution.name,
        deferred_price=_money(execution.deferred_price),
        currency=execution.currency,
        tenor_months=execution.tenor_months,
    )
    execution.wad_token_id = wad.token_id
    execution.wad_signature = wad.signature
    if execution.application:
        execution.application.wad_text = wad.text
        execution.application.wad_accepted_at = datetime.now(UTC)
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=institution.id,
        application_id=execution.application_id,
        kind=VaultCertificateKind.CMP,
        certificate_number=cmp.token_id,
        source="bti_token_engine",
        payload={**cmp.payload, "signature": cmp.signature},
    )
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=institution.id,
        application_id=execution.application_id,
        kind=VaultCertificateKind.WAD,
        certificate_number=wad.token_id,
        source="bti_token_engine",
        payload={**wad.payload, "signature": wad.signature},
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.WAD_UNDERTAKING,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="customer",
        actor_to="bank",
        payload={"wad_token_id": wad.token_id, "cmp_token_id": cmp.token_id},
        institution_id=institution.id,
        application_id=execution.application_id,
    )
    if not execution.appoint_sasc:
        return
    agency = stamp_wakalah(
        execution_id=execution.id,
        customer_id=customer.id,
        customer_name=customer.full_name,
        institution_name=institution.name,
        agency_role=execution.agency_role,
    )
    execution.wakalah_token_id = agency.token_id
    execution.wakalah_signature = agency.signature
    kind = VaultCertificateKind.RASUL if agency.kind == "rasul" else VaultCertificateKind.WAKALAH
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=institution.id,
        application_id=execution.application_id,
        kind=kind,
        certificate_number=agency.token_id,
        source="bti_token_engine",
        payload={**agency.payload, "signature": agency.signature},
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.SASC_APPOINTMENT,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="customer",
        actor_to="sedania",
        payload={"token_id": agency.token_id, "agency_role": execution.agency_role, "agency_party": SASC_PARTY_CODE},
        institution_id=institution.id,
        application_id=execution.application_id,
    )


def _run_as_sidq_legs(
    db: Session,
    execution: TawarruqExecution,
    institution: Institution,
    customer: Customer,
    amount: Decimal,
    profit: Decimal,
    deferred: Decimal,
) -> None:
    client = get_sedania_client()
    execution.status = ExecutionStatus.SPOT_PURCHASE
    purchase = client.purchase(
        SedaniaPurchaseRequest(
            execution_id=execution.id,
            institution_code=institution.code,
            customer_id=customer.id,
            amount=amount,
            currency=execution.currency,
        )
    )
    if not purchase.success or not purchase.batch_id or not purchase.certificate_number:
        raise IntegrationError(purchase.error_message or "Sedania purchase did not return a batch")
    execution.sedania_batch_id = purchase.batch_id
    execution.supplier_ref = str(purchase.payload.get("supplier") or SUPPLIER_REF)
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=institution.id,
        application_id=execution.application_id,
        kind=VaultCertificateKind.PURCHASE,
        certificate_number=purchase.certificate_number,
        source="sedania",
        payload=purchase.payload,
        source_url=purchase.certificate_url,
        serial_numbers=purchase.serial_numbers,
        batch_id=purchase.batch_id,
    )
    store_trade_pack(db, execution, institution=institution, customer=customer)
    log_shariah_step(
        db,
        step_id=ShariahStepId.CONSTRUCTIVE_POSSESSION,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="sedania",
        actor_to="bank",
        payload={
            "batch_id": purchase.batch_id,
            "serial_numbers": purchase.serial_numbers,
            "qabd_hukmi": True,
            "purchase_order": execution.purchase_order_ref,
            "delivery_order": execution.delivery_order_ref,
        },
        asset_ref_no=purchase.batch_id,
        institution_id=institution.id,
        application_id=execution.application_id,
    )

    execution.status = ExecutionStatus.DEFERRED_MURABAHAH
    murabahah = client.transfer_murabahah(
        SedaniaMurabahahRequest(
            execution_id=execution.id,
            batch_id=purchase.batch_id,
            cost_price=amount,
            profit_amount=profit,
            deferred_price=deferred,
            currency=execution.currency,
            customer_id=customer.id,
            tenor_months=execution.tenor_months,
        )
    )
    if not murabahah.success or not murabahah.certificate_number:
        raise IntegrationError(murabahah.error_message or "Sedania Murabahah transfer failed")
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=institution.id,
        application_id=execution.application_id,
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
        actor_from="bank",
        actor_to="customer",
        payload={
            "cost_price": str(amount),
            "profit_amount": str(profit),
            "deferred_price": str(deferred),
            "trading_ecert": execution.trading_ecert_ref,
        },
        asset_ref_no=purchase.batch_id,
        institution_id=institution.id,
        application_id=execution.application_id,
    )
    if execution.application:
        execution.application.current_phase = TransactionPhase.PHASE_2_MURABAHA


def _liquidate_via_sasc(
    db: Session,
    execution: TawarruqExecution,
    institution: Institution,
    customer: Customer,
    amount: Decimal,
) -> None:
    if not execution.appoint_sasc or not execution.wakalah_token_id:
        raise HTTPException(
            status_code=409,
            detail="Independent sale requires the customer to appoint SEDANIA As Salam Capital.",
        )
    if not execution.sedania_batch_id:
        raise HTTPException(status_code=409, detail="No AS SIDQ batch is available to sell.")
    client = get_sedania_client()
    execution.status = ExecutionStatus.SPOT_LIQUIDATION
    liquidation = client.liquidate(
        SedaniaLiquidateRequest(
            execution_id=execution.id,
            batch_id=execution.sedania_batch_id,
            spot_amount=amount,
            currency=execution.currency,
            wakeel_ref=execution.wakalah_token_id,
            agency_role=execution.agency_role,
            agency_party=execution.agency_party,
        )
    )
    if not liquidation.success or not liquidation.certificate_number:
        raise IntegrationError(liquidation.error_message or "Sedania liquidation failed")
    execution.purchaser_ref = str(liquidation.payload.get("independent_buyer") or DEFAULT_PURCHASER)
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=institution.id,
        application_id=execution.application_id,
        kind=VaultCertificateKind.LIQUIDATION,
        certificate_number=liquidation.certificate_number,
        source="sedania",
        payload=liquidation.payload,
        source_url=liquidation.certificate_url,
        batch_id=execution.sedania_batch_id,
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.THIRD_PARTY_LIQUIDATION,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="sedania",
        actor_to=execution.purchaser_ref,
        payload={
            "certificate_number": liquidation.certificate_number,
            "agency_role": execution.agency_role,
            "independent_buyer": execution.purchaser_ref,
        },
        asset_ref_no=execution.sedania_batch_id,
        institution_id=institution.id,
        application_id=execution.application_id,
    )
    if execution.application:
        execution.application.current_phase = TransactionPhase.PHASE_3_LIQUIDATION


def _record_muqassah(
    db: Session,
    execution: TawarruqExecution,
    institution: Institution,
    customer: Customer,
    amount: Decimal,
) -> None:
    refs = trade_pack_refs(execution.id)
    execution.status = ExecutionStatus.MUQASSAH
    execution.muqassah_ref = refs["muqassah"]
    execution.muqassah_at = datetime.now(UTC)
    payload = {
        "title": "Muqassah set-off instruction",
        "ref": execution.muqassah_ref,
        "purchaser": execution.purchaser_ref or DEFAULT_PURCHASER,
        "seller": execution.supplier_ref or SUPPLIER_REF,
        "bank": institution.name,
        "customer_name": customer.full_name,
        "amount": str(amount),
        "currency": execution.currency,
        "authorization": (
            f"{execution.purchaser_ref or DEFAULT_PURCHASER} authorizes {institution.name} "
            f"to pay {customer.full_name} on its behalf."
        ),
        "set_off": (
            f"{execution.purchaser_ref or DEFAULT_PURCHASER} agrees to pay the commodity seller "
            f"({execution.supplier_ref or SUPPLIER_REF}) for set-off (muqassah)."
        ),
        "issued_at": execution.muqassah_at.isoformat(),
    }
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=institution.id,
        application_id=execution.application_id,
        kind=VaultCertificateKind.MUQASSAH,
        certificate_number=execution.muqassah_ref,
        source="bank_core",
        payload=payload,
        batch_id=execution.sedania_batch_id,
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.MUQASSAH_SET_OFF,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from=execution.purchaser_ref or DEFAULT_PURCHASER,
        actor_to="bank",
        payload={"muqassah_ref": execution.muqassah_ref, "amount": str(amount)},
        asset_ref_no=execution.sedania_batch_id,
        institution_id=institution.id,
        application_id=execution.application_id,
    )
    dispatch_webhook_event(
        db,
        institution_id=institution.id,
        event=WebhookEvent.MUQASSAH_COMPLETED,
        data={"execution_id": execution.id, "muqassah_ref": execution.muqassah_ref},
    )


def _credit_casa(
    db: Session,
    execution: TawarruqExecution,
    institution: Institution,
    customer: Customer,
    amount: Decimal,
) -> None:
    refs = trade_pack_refs(execution.id)
    execution.status = ExecutionStatus.CASA_CREDIT
    execution.casa_account = execution.casa_account or customer.wallet_number
    execution.casa_ref = refs["casa"]
    execution.casa_credited_at = datetime.now(UTC)
    payload = {
        "title": "CASA credit advice",
        "ref": execution.casa_ref,
        "casa_account": execution.casa_account,
        "customer_name": customer.full_name,
        "institution_name": institution.name,
        "amount": str(amount),
        "currency": execution.currency,
        "issued_at": execution.casa_credited_at.isoformat(),
        "narrative": (
            f"{institution.name} credits {execution.casa_account} with {execution.currency} {amount} "
            "after the independent AS SIDQ sale"
            + (" and muqassah set-off." if execution.muqassah_ref else ".")
        ),
    }
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=institution.id,
        application_id=execution.application_id,
        kind=VaultCertificateKind.CASA_ADVICE,
        certificate_number=execution.casa_ref,
        source="bank_core",
        payload=payload,
        batch_id=execution.sedania_batch_id,
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.CASA_CREDIT,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="bank",
        actor_to="customer",
        payload={"casa_account": execution.casa_account, "casa_ref": execution.casa_ref, "amount": str(amount)},
        institution_id=institution.id,
        application_id=execution.application_id,
    )
    dispatch_webhook_event(
        db,
        institution_id=institution.id,
        event=WebhookEvent.CASA_CREDITED,
        data={
            "execution_id": execution.id,
            "casa_account": execution.casa_account,
            "casa_ref": execution.casa_ref,
            "amount": str(amount),
            "currency": execution.currency,
        },
    )
