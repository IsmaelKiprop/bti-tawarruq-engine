"""Apply the published As-Sidq trading API to a Tawarruq execution."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.enums import (
    ApplicationStatus,
    AuditActor,
    ExecutionPath,
    ExecutionStatus,
    PhysicalDeliveryStatus,
    SedaniaDeliveryMode,
    SedaniaFlowVariant,
    ShariahStepId,
    TransactionPhase,
    VaultCertificateKind,
    WebhookEvent,
)
from tawarruq.integrations.base import IntegrationError
from tawarruq.integrations.sedania.client import (
    CANCEL_REASONS,
    STATUS_CANCELED,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_KEEP,
    STATUS_NOT_FOUND,
    STATUS_PENDING,
    STATUS_VALIDATION,
    SedaniaApiResult,
    SedaniaCancelSubmit,
    SedaniaTradeSubmit,
    alphanumeric_ref,
    certificate_password,
    get_sedania_client,
    parse_asidq_response,
)
from tawarruq.models.customer import Customer
from tawarruq.models.execution import TawarruqExecution
from tawarruq.models.institution import Institution
from tawarruq.services.audit_service import log_audit
from tawarruq.services.certificate_vault_service import store_certificate
from tawarruq.services.shariah_audit_service import log_shariah_step

logger = logging.getLogger(__name__)

SUPPLIER_REF = "TELECOMMUNICATION_AIRTIME_AGGREGATOR"
DEFAULT_PURCHASER = "SEDANIA_RANDOM_PURCHASER"
PENDING_STATUSES = {
    ExecutionStatus.PENDING_AS_SIDQ,
    ExecutionStatus.SPOT_PURCHASE,
    ExecutionStatus.CANCELLATION_PENDING,
}


def make_ref_no(execution: TawarruqExecution) -> str:
    if execution.as_sidq_ref_no:
        return execution.as_sidq_ref_no
    return alphanumeric_ref(execution.id.replace("-", ""), prefix="BTI")


def _money(value: Decimal | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _product_code(execution: TawarruqExecution) -> str:
    return (execution.as_sidq_product_code or get_settings().sedania_product_code or "P01").strip() or "P01"


def _trade_request(execution: TawarruqExecution, customer: Customer) -> SedaniaTradeSubmit:
    keep = "Y" if execution.delivery_mode == SedaniaDeliveryMode.PHYSICAL else "N"
    amount = _money(execution.amount)
    profit = _money(execution.profit_amount)
    rate_pct = None
    if Decimal(str(execution.amount)) > 0 and profit > 0:
        rate_pct = (profit / amount) * Decimal("100")
    return SedaniaTradeSubmit(
        ref_no=make_ref_no(execution),
        cust_name=(customer.full_name or "Customer").strip()[:100],
        cust_id=(customer.national_id or customer.phone or customer.id)[:100],
        trading_amount=amount,
        product_code=_product_code(execution),
        currency=execution.currency or "MYR",
        profit_rate_pct=rate_pct,
        profit_amount=profit,
        keep_commodity=keep,
    )


def submit_as_sidq_trade(
    db: Session,
    execution: TawarruqExecution,
    institution: Institution,
    customer: Customer,
) -> str:
    """POST /api/v1/trading. Returns 'pending' or 'complete'.

    Mock completes immediately via Get Status. Live waits for the callback.
    """
    client = get_sedania_client()
    request = _trade_request(execution, customer)
    execution.as_sidq_ref_no = request.ref_no
    execution.as_sidq_product_code = request.product_code
    execution.status = ExecutionStatus.SPOT_PURCHASE
    result = client.submit_trade(request)
    execution.as_sidq_status_code = result.status_code
    execution.as_sidq_status_desc = result.status_desc
    if result.status_code == STATUS_VALIDATION:
        recovered = client.get_status(request.ref_no)
        if recovered.status_code == STATUS_NOT_FOUND:
            raise IntegrationError(result.description or "As-Sidq rejected this ref_no.")
        result = recovered
    if result.status_code not in {200, STATUS_PENDING, STATUS_COMPLETE, STATUS_KEEP} and not result.pending:
        raise IntegrationError(result.description or f"As-Sidq trading failed ({result.status_code})")

    log_audit(
        db,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor=AuditActor.SYSTEM,
        action="asidq.trading.submitted",
        details=f"ref_no={request.ref_no} status_code={result.status_code}",
        institution_id=institution.id,
    )

    if get_settings().is_live_sedania and (result.accepted or result.pending or result.status_code == 200):
        status = client.get_status(request.ref_no)
        if status.callback or status.status_code in {STATUS_COMPLETE, STATUS_KEEP, STATUS_FAILED, STATUS_CANCELED}:
            apply_as_sidq_result(db, execution, status)
            return "complete" if execution.status not in PENDING_STATUSES else "pending"
        execution.status = ExecutionStatus.PENDING_AS_SIDQ
        execution.as_sidq_status_code = STATUS_PENDING
        execution.as_sidq_status_desc = "PENDING"
        db.flush()
        return "pending"

    completed = client.get_status(request.ref_no)
    apply_as_sidq_result(db, execution, completed)
    return "complete"


def refresh_as_sidq_status(db: Session, execution: TawarruqExecution) -> TawarruqExecution:
    if not execution.as_sidq_ref_no:
        raise HTTPException(status_code=409, detail="This facility has not been submitted to As-Sidq.")
    if execution.created_at:
        created = execution.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if datetime.now(UTC) - created > timedelta(minutes=30) and execution.status in PENDING_STATUSES:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = "As-Sidq trade still pending after 30 minutes."
            if execution.application:
                execution.application.status = ApplicationStatus.FAILED
            db.flush()
            return execution
    client = get_sedania_client()
    result = client.get_status(execution.as_sidq_ref_no)
    apply_as_sidq_result(db, execution, result)
    return execution


def request_as_sidq_cancel(
    db: Session,
    execution: TawarruqExecution,
    *,
    reason: str,
    other_reason: str | None = None,
) -> TawarruqExecution:
    if reason not in CANCEL_REASONS:
        raise HTTPException(status_code=400, detail="Cancellation reason is not in the As-Sidq list.")
    if not execution.as_sidq_ref_no:
        raise HTTPException(status_code=409, detail="This facility has not been submitted to As-Sidq.")
    client = get_sedania_client()
    result = client.cancel(
        SedaniaCancelSubmit(ref_no=execution.as_sidq_ref_no, reason=reason, other_reason=other_reason)
    )
    execution.as_sidq_cancel_reason = reason
    if result.request_id is not None:
        execution.as_sidq_cancel_request_id = str(result.request_id)
    execution.as_sidq_status_code = result.status_code
    execution.as_sidq_status_desc = result.status_desc
    if result.status_code in {202, STATUS_PENDING}:
        execution.status = ExecutionStatus.CANCELLATION_PENDING
    elif result.status_code in {400, 401, 404, 409, 422}:
        raise HTTPException(status_code=400, detail=result.description or result.status_desc)
    log_audit(
        db,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor=AuditActor.HUMAN,
        action="asidq.cancellation.submitted",
        details=f"ref_no={execution.as_sidq_ref_no} reason={reason}",
        institution_id=execution.institution_id,
    )
    if not get_settings().is_live_sedania:
        apply_as_sidq_result(db, execution, client.get_status(execution.as_sidq_ref_no))
    db.flush()
    return execution


def apply_as_sidq_callback(db: Session, payload: dict[str, Any]) -> TawarruqExecution:
    result = parse_asidq_response(payload)
    ref_no = result.ref_no or str(payload.get("ref_no") or "")
    if not ref_no:
        raise HTTPException(status_code=400, detail="Callback is missing ref_no.")
    execution = (
        db.query(TawarruqExecution)
        .filter(TawarruqExecution.as_sidq_ref_no == ref_no)
        .first()
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="No facility matches this As-Sidq ref_no.")
    apply_as_sidq_result(db, execution, result)
    db.flush()
    return execution


def apply_as_sidq_result(db: Session, execution: TawarruqExecution, result: SedaniaApiResult) -> None:
    execution.as_sidq_status_code = result.status_code
    execution.as_sidq_status_desc = result.status_desc
    callback = result.callback or {}
    if callback:
        execution.as_sidq_trading_status = str(callback.get("trading_status") or result.status_desc)
        execution.as_sidq_cert_url = str(callback.get("cert") or "") or execution.as_sidq_cert_url
        cert_no = callback.get("cert_no") if isinstance(callback.get("cert_no"), dict) else {}
        execution.as_sidq_cert_a = cert_no.get("A") or execution.as_sidq_cert_a
        execution.as_sidq_cert_b = cert_no.get("B") or execution.as_sidq_cert_b
        execution.as_sidq_cert_c = cert_no.get("C") or execution.as_sidq_cert_c
        if callback.get("delivery_order_no"):
            execution.delivery_order_ref = str(callback["delivery_order_no"])
        if callback.get("supplying_party"):
            execution.supplier_ref = str(callback["supplying_party"])
        keep_now = result.status_code == STATUS_KEEP or result.status_desc == "KEEP"
        if callback.get("buying_party") and not keep_now:
            execution.purchaser_ref = str(callback["buying_party"])
        execution.sedania_batch_id = execution.sedania_batch_id or str(
            callback.get("delivery_order_no") or execution.as_sidq_ref_no
        )
        execution.as_sidq_callback_json = json.dumps(result.raw, default=str)

    if result.status_code == STATUS_FAILED or result.status_desc == "FAILED":
        _fail(execution, result.description or "As-Sidq trading failed.")
        return
    if result.status_code == STATUS_CANCELED or result.status_desc in {"CANCELED", "CANCELLED"}:
        execution.status = ExecutionStatus.CANCELLED
        execution.error_message = result.description or "As-Sidq cancelled this trade."
        execution.completed_at = datetime.now(UTC)
        if execution.application:
            execution.application.status = ApplicationStatus.FAILED
        return
    if result.status_code in {STATUS_PENDING, 399} or result.status_desc in {"PENDING", "CANCELLATION_PENDING"}:
        if result.status_code == 399:
            execution.status = ExecutionStatus.CANCELLATION_PENDING
        elif execution.status not in PENDING_STATUSES:
            execution.status = ExecutionStatus.PENDING_AS_SIDQ
        return
    if result.status_code == 201 or result.status_desc == "CANCELLATION_REJECTED":
        if execution.status == ExecutionStatus.CANCELLATION_PENDING:
            execution.status = ExecutionStatus.COMPLETED if execution.casa_ref else ExecutionStatus.PENDING_AS_SIDQ
        return
    finished = result.status_desc in {"COMPLETE", "KEEP"} or result.status_code == STATUS_KEEP or (
        result.status_code == STATUS_COMPLETE and bool(result.callback)
    )
    if not finished:
        return
    if execution.status in {ExecutionStatus.COMPLETED, ExecutionStatus.AWAITING_SETTLEMENT, ExecutionStatus.READY_FOR_SACCO_DISBURSEMENT}:
        return
    if execution.as_sidq_callback_json is None and result.raw:
        execution.as_sidq_callback_json = json.dumps(result.raw, default=str)

    keep = result.status_code == STATUS_KEEP or result.status_desc == "KEEP" or execution.delivery_mode == SedaniaDeliveryMode.PHYSICAL
    _vault_asidq_legs(db, execution, callback, keep=keep)
    _download_master_cert(db, execution)
    from tawarruq.services.sedania_financing_service import store_trade_pack

    institution = execution.institution
    customer = execution.customer
    if institution is None or customer is None:
        raise IntegrationError("Execution is missing institution or customer for As-Sidq completion.")
    store_trade_pack(db, execution, institution=institution, customer=customer)
    if execution.delivery_order_ref is None and callback.get("delivery_order_no"):
        execution.delivery_order_ref = str(callback["delivery_order_no"])
    _log_trade_shariah(db, execution, callback, keep=keep)

    if keep:
        execution.delivery_mode = SedaniaDeliveryMode.PHYSICAL
        execution.physical_delivery_requested = True
        execution.physical_delivery_status = PhysicalDeliveryStatus.AWAITING_SETTLEMENT
        execution.status = ExecutionStatus.AWAITING_SETTLEMENT
        execution.cash_disbursement = "withheld_physical"
        if execution.application:
            execution.application.current_phase = TransactionPhase.PHASE_4_REPAYMENT
        return

    if execution.path == ExecutionPath.SACCO:
        from tawarruq.services.sacco_execute_service import finish_sacco_after_asidq

        finish_sacco_after_asidq(db, execution)
        return
    from tawarruq.services.sedania_financing_service import finish_bank_after_asidq

    finish_bank_after_asidq(db, execution)


def _fail(execution: TawarruqExecution, message: str) -> None:
    execution.status = ExecutionStatus.FAILED
    execution.error_message = message
    if execution.application:
        execution.application.status = ApplicationStatus.FAILED


def _vault_asidq_legs(
    db: Session,
    execution: TawarruqExecution,
    callback: dict[str, Any],
    *,
    keep: bool,
) -> None:
    existing = {item.kind for item in (execution.certificates or [])}
    cert_no = callback.get("cert_no") if isinstance(callback.get("cert_no"), dict) else {}
    legs = [
        (VaultCertificateKind.PURCHASE, cert_no.get("A") or execution.as_sidq_cert_a, "Certificate A (Trading Leg 1)"),
        (VaultCertificateKind.MURABAHAH, cert_no.get("B") or execution.as_sidq_cert_b, "Certificate B (Trading Leg 2)"),
    ]
    if not keep:
        legs.append(
            (VaultCertificateKind.LIQUIDATION, cert_no.get("C") or execution.as_sidq_cert_c, "Certificate C (Trading Leg 3)")
        )
    source_url = str(callback.get("cert") or execution.as_sidq_cert_url or "") or None
    for kind, number, title in legs:
        if not number or kind in existing:
            continue
        store_certificate(
            db,
            execution_id=execution.id,
            institution_id=execution.institution_id,
            application_id=execution.application_id,
            kind=kind,
            certificate_number=str(number),
            source="as_sidq",
            payload={
                "title": title,
                "certificate_number": number,
                "ref_no": execution.as_sidq_ref_no,
                "delivery_order_no": callback.get("delivery_order_no") or execution.delivery_order_ref,
                "commodity_type": callback.get("commodity_type") or "TELCO_AIRTIME",
                "value": callback.get("value"),
                "unit": callback.get("unit"),
                "supplying_party": callback.get("supplying_party"),
                "buying_party": callback.get("buying_party"),
                "qabd_hukmi": kind == VaultCertificateKind.PURCHASE,
            },
            source_url=source_url,
            serial_numbers=[str(callback.get("unit") or 1)] if kind == VaultCertificateKind.PURCHASE else None,
            batch_id=execution.sedania_batch_id,
        )


def _download_master_cert(db: Session, execution: TawarruqExecution) -> None:
    if not execution.as_sidq_cert_url:
        return
    existing = {item.kind for item in (execution.certificates or [])}
    if VaultCertificateKind.ASIDQ_CERT in existing:
        return
    client = get_sedania_client()
    pdf: bytes | None = None
    try:
        pdf = client.download_certificate(execution.as_sidq_cert_url)
    except Exception:
        logger.exception("Could not download As-Sidq certificate for %s", execution.as_sidq_ref_no)
    payload: dict[str, Any] = {
        "title": "As-Sidq master certificate",
        "ref_no": execution.as_sidq_ref_no,
        "cert_url": execution.as_sidq_cert_url,
        "password": certificate_password(execution.as_sidq_ref_no or ""),
    }
    if pdf:
        import base64

        payload["pdf_base64"] = base64.b64encode(pdf).decode("ascii")
        payload["pdf_password"] = payload["password"]
    store_certificate(
        db,
        execution_id=execution.id,
        institution_id=execution.institution_id,
        application_id=execution.application_id,
        kind=VaultCertificateKind.ASIDQ_CERT,
        certificate_number=execution.as_sidq_cert_a or execution.as_sidq_ref_no or execution.id,
        source="as_sidq",
        payload=payload,
        source_url=execution.as_sidq_cert_url,
        batch_id=execution.sedania_batch_id,
    )


def _log_trade_shariah(
    db: Session,
    execution: TawarruqExecution,
    callback: dict[str, Any],
    *,
    keep: bool,
) -> None:
    log_shariah_step(
        db,
        step_id=ShariahStepId.CONSTRUCTIVE_POSSESSION,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="sedania",
        actor_to="bank" if execution.path == ExecutionPath.BANK_FINANCING else "sacco",
        payload={
            "ref_no": execution.as_sidq_ref_no,
            "delivery_order_no": execution.delivery_order_ref,
            "cert_a": execution.as_sidq_cert_a,
            "qabd_hukmi": True,
        },
        asset_ref_no=execution.as_sidq_ref_no,
        institution_id=execution.institution_id,
        application_id=execution.application_id,
    )
    log_shariah_step(
        db,
        step_id=ShariahStepId.OWNERSHIP_TRANSFER,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="bank" if execution.path == ExecutionPath.BANK_FINANCING else "sacco",
        actor_to="customer",
        payload={
            "cert_b": execution.as_sidq_cert_b,
            "cost_price": str(execution.amount),
            "profit_amount": str(execution.profit_amount),
            "deferred_price": str(execution.deferred_price),
        },
        asset_ref_no=execution.as_sidq_ref_no,
        institution_id=execution.institution_id,
        application_id=execution.application_id,
    )
    if keep:
        return
    log_shariah_step(
        db,
        step_id=ShariahStepId.THIRD_PARTY_LIQUIDATION,
        entity_type="tawarruq_execution",
        entity_id=execution.id,
        actor_from="sedania",
        actor_to=execution.purchaser_ref or DEFAULT_PURCHASER,
        payload={
            "cert_c": execution.as_sidq_cert_c,
            "independent_buyer": execution.purchaser_ref or DEFAULT_PURCHASER,
        },
        asset_ref_no=execution.as_sidq_ref_no,
        institution_id=execution.institution_id,
        application_id=execution.application_id,
    )
