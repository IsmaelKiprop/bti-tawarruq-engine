from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from tawarruq.enums import ApplicationStatus, AuditActor, InstallmentStatus, ShariahStepId, TransactionPhase, WebhookEvent
from tawarruq.integrations.base import IntegrationError
from tawarruq.integrations.mpesa.daraja import get_daraja_client
from tawarruq.services.integration_config_service import resolve_integration_profile
from tawarruq.models.application import FinancingApplication
from tawarruq.models.kenya_flow import RepaymentInstallment
from tawarruq.services.audit_service import log_audit
from tawarruq.services.kenya_flow_service import verify_possession
from tawarruq.services.repayment_service import collect_repayment
from tawarruq.services.shariah_audit_service import log_shariah_step
from tawarruq.services.wallet_service import complete_wallet_from_b2c_callback


def handle_mpesa_b2c_result(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    """Process Daraja B2C ResultURL callback."""
    result = body.get("Result") or body
    wallet = complete_wallet_from_b2c_callback(
        db,
        originator_conversation_id=result.get("OriginatorConversationID"),
        conversation_id=result.get("ConversationID"),
        result_code=int(result.get("ResultCode", -1)),
        result_desc=str(result.get("ResultDesc", "")),
        mpesa_receipt=_extract_b2c_receipt(result),
    )
    return {"processed": wallet is not None, "wallet_id": wallet.id if wallet else None, "status": wallet.status if wallet else None}


def _extract_b2c_receipt(result: dict[str, Any]) -> str | None:
    parameters = result.get("ResultParameters", {}).get("ResultParameter") or []
    for param in parameters:
        if param.get("Key") == "TransactionReceipt":
            return str(param.get("Value"))
    return result.get("TransactionID")


def handle_mpesa_stk_callback(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    """Process Daraja STK Push callback for repayment collection."""
    callback = (body.get("Body") or {}).get("stkCallback") or body.get("stkCallback") or body
    checkout_id = callback.get("CheckoutRequestID")
    result_code = int(callback.get("ResultCode", -1))

    if not checkout_id:
        return {"processed": False, "reason": "missing CheckoutRequestID"}

    installment = (
        db.query(RepaymentInstallment)
        .filter(RepaymentInstallment.payment_ref == checkout_id)
        .first()
    )
    if not installment:
        return {"processed": False, "reason": "installment not found", "checkout_request_id": checkout_id}

    if result_code != 0:
        installment.status = InstallmentStatus.DUE
        log_audit(
            db,
            entity_type="repayment_installment",
            entity_id=installment.id,
            actor=AuditActor.MNO,
            action="repayment.stk_failed",
            details=str(callback.get("ResultDesc", "")),
        )
        db.flush()
        return {"processed": True, "installment_id": installment.id, "status": installment.status}

    mpesa_receipt = _extract_stk_receipt(callback)
    installment.status = InstallmentStatus.PAID
    installment.paid_at = datetime.now(UTC)
    if mpesa_receipt:
        installment.payment_ref = mpesa_receipt

    contract = installment.contract
    application = db.get(FinancingApplication, contract.application_id) if contract else None

    if application and application.customer_id:
        from tawarruq.services import mobile_inbox_service

        mobile_inbox_service.notify_account_by_customer(
            db,
            application.customer_id,
            kind="repayment",
            title="Repayment received",
            body=f"Installment payment confirmed"
            + (f" (ref {mpesa_receipt})." if mpesa_receipt else "."),
            application_id=application.id,
        )

    log_shariah_step(
        db,
        step_id=ShariahStepId.REPAYMENT_RECEIVED,
        entity_type="repayment_installment",
        entity_id=installment.id,
        actor_from=application.customer_ref if application else "customer",
        actor_to=application.institution.name if application else "institution",
        payload={
            "installment_number": installment.installment_number,
            "amount": str(installment.amount),
            "payment_ref": installment.payment_ref,
            "source": "stk_callback",
        },
        asset_ref_no=installment.payment_ref,
    )

    if application and contract:
        unpaid = [i for i in contract.installments if i.status != InstallmentStatus.PAID]
        if not unpaid:
            application.status = ApplicationStatus.COMPLETED
            application.current_phase = TransactionPhase.COMPLETED

    db.flush()
    return {"processed": True, "installment_id": installment.id, "status": installment.status}


def _extract_stk_receipt(callback: dict[str, Any]) -> str | None:
    metadata = callback.get("CallbackMetadata", {}).get("Item") or []
    for item in metadata:
        if item.get("Name") == "MpesaReceiptNumber":
            return str(item.get("Value"))
    return callback.get("CheckoutRequestID")


def handle_mno_possession_callback(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    """
    Process MNO partner possession webhook.

    Expected body: { "batch_id": "...", "receipt_id": "...", "status": "verified", "transaction_id": "..." }
    """
    batch_id = body.get("batch_id") or body.get("BatchId")
    receipt_id = body.get("receipt_id") or body.get("ReceiptId") or body.get("mno_receipt_id")
    transaction_id = body.get("transaction_id")
    status = str(body.get("status", "")).lower()

    if not batch_id or status not in ("verified", "confirmed", "success"):
        return {"processed": False, "reason": "invalid or unverified payload"}

    from tawarruq.models.kenya_flow import AssetBatch
    from tawarruq.models.transaction import CommodityTransaction

    batch = db.query(AssetBatch).filter(AssetBatch.batch_id == batch_id).first()
    if not batch:
        return {"processed": False, "reason": "batch not found", "batch_id": batch_id}

    leg = batch.leg
    transaction = db.get(CommodityTransaction, leg.transaction_id if leg else transaction_id)
    if not transaction:
        return {"processed": False, "reason": "transaction not found"}

    verify_possession(
        db,
        transaction.id,
        batch_id=batch_id,
        mno_receipt_id=receipt_id,
        actor=AuditActor.MNO,
    )
    return {"processed": True, "transaction_id": transaction.id, "batch_id": batch_id}


def initiate_stk_repayment(db: Session, installment_id: str, *, actor: AuditActor = AuditActor.SYSTEM) -> RepaymentInstallment:
    """Initiate live M-Pesa STK Push for an installment."""
    installment = db.get(RepaymentInstallment, installment_id)
    if not installment:
        raise ValueError("Installment not found")
    if installment.status == InstallmentStatus.PAID:
        return installment

    contract = installment.contract
    application = db.get(FinancingApplication, contract.application_id) if contract else None
    if not application or not application.customer_id:
        raise ValueError("Customer required for STK repayment")

    profile = resolve_integration_profile(db, application.institution_id)
    if not profile.is_live or not profile.mpesa_configured:
        return collect_repayment(db, installment_id, actor=actor)

    from tawarruq.models.customer import Customer

    customer = db.get(Customer, application.customer_id)
    if not customer:
        raise ValueError("Customer not found")
    phone = customer.wallet_number
    daraja = get_daraja_client(profile)
    try:
        result = daraja.stk_push(
            phone=phone,
            amount=installment.amount,
            account_reference=f"TWQ{installment.installment_number}",
            transaction_desc="TawarruqRepay",
        )
    except IntegrationError as exc:
        raise ValueError(str(exc)) from exc

    checkout_id = result.get("CheckoutRequestID")
    installment.payment_ref = checkout_id
    installment.status = InstallmentStatus.AWAITING_PAYMENT
    db.flush()
    if application.customer_id:
        from tawarruq.services import mobile_inbox_service

        mobile_inbox_service.notify_account_by_customer(
            db,
            application.customer_id,
            kind="stk",
            title="M-Pesa STK sent",
            body="Confirm the payment prompt on your phone to complete this installment.",
            application_id=application.id,
        )
    log_audit(
        db,
        entity_type="repayment_installment",
        entity_id=installment.id,
        actor=actor,
        action="repayment.stk_initiated",
        evidence_ref=checkout_id,
        details=f"amount={installment.amount}",
    )
    return installment
