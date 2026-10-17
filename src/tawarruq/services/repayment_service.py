import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from tawarruq.enums import (
    ApplicationStatus,
    AuditActor,
    InstallmentStatus,
    ShariahStepId,
    TransactionPhase,
    WebhookEvent,
)
from tawarruq.models.application import FinancingApplication, FinancingOffer
from tawarruq.models.kenya_flow import MurabahaContract, RepaymentInstallment
from tawarruq.services.audit_service import log_audit
from tawarruq.services.shariah_audit_service import log_shariah_step
from tawarruq.services.webhook_service import dispatch_webhook_event


def _document_hash(application_id: str, offer: FinancingOffer, installment_count: int) -> str:
    raw = f"{application_id}:{offer.cost_price}:{offer.total_payable}:{installment_count}"
    return hashlib.sha256(raw.encode()).hexdigest()


def create_murabaha_contract(
    db: Session,
    application_id: str,
    installment_count: int | None = None,
    actor: AuditActor = AuditActor.SYSTEM,
) -> MurabahaContract:
    application = db.get(FinancingApplication, application_id)
    if not application or not application.offer:
        raise ValueError("Application with offer required")
    if application.murabaha_contract:
        return application.murabaha_contract

    offer = application.offer
    count = installment_count if installment_count else application.term_months
    offer.installment_count = count
    doc_hash = _document_hash(application.id, offer, count)
    contract = MurabahaContract(
        application_id=application.id,
        offer_id=offer.id,
        document_hash=doc_hash,
        installment_count=count,
    )
    db.add(contract)
    db.flush()

    log_shariah_step(
        db,
        step_id=ShariahStepId.MURABAHA_OFFER,
        entity_type="murabaha_contract",
        entity_id=contract.id,
        actor_from=application.institution.name,
        actor_to=application.customer_ref,
        payload={
            "document_hash": doc_hash,
            "total_payable": str(offer.total_payable),
            "installments": count,
        },
        asset_ref_no=doc_hash[:16],
    )
    log_audit(
        db,
        entity_type="murabaha_contract",
        entity_id=contract.id,
        actor=actor,
        action="murabaha.contract_created",
        evidence_ref=doc_hash[:16],
    )
    return contract


def sign_murabaha_contract(
    db: Session,
    application_id: str,
    signature_ref: str | None = None,
    actor: AuditActor = AuditActor.CUSTOMER,
) -> MurabahaContract:
    application = db.get(FinancingApplication, application_id)
    if not application or not application.murabaha_contract:
        raise ValueError("Murabaha contract not found")

    contract = application.murabaha_contract
    if contract.signed_at:
        return contract

    contract.signature_ref = signature_ref if signature_ref else f"SIG-{uuid.uuid4().hex[:12].upper()}"
    contract.signed_at = datetime.now(UTC)
    db.flush()

    log_shariah_step(
        db,
        step_id=ShariahStepId.CUSTOMER_ACCEPTANCE,
        entity_type="murabaha_contract",
        entity_id=contract.id,
        actor_from=application.customer_ref,
        actor_to=application.institution.name,
        payload={
            "signature_ref": contract.signature_ref,
            "signed_at": contract.signed_at.isoformat(),
        },
        asset_ref_no=contract.signature_ref,
    )
    log_audit(
        db,
        entity_type="murabaha_contract",
        entity_id=contract.id,
        actor=actor,
        action="murabaha.signed",
        evidence_ref=contract.signature_ref,
    )
    return contract


def generate_repayment_schedule(
    db: Session,
    application_id: str,
    actor: AuditActor = AuditActor.SYSTEM,
) -> list[RepaymentInstallment]:
    application = db.get(FinancingApplication, application_id)
    if not application or not application.murabaha_contract:
        raise ValueError("Signed Murabaha contract required")

    contract = application.murabaha_contract
    if contract.installments:
        return contract.installments

    total = Decimal(str(application.offer.total_payable))
    count = contract.installment_count
    installment_amount = (total / Decimal(count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    remainder = total - (installment_amount * count)

    installments = []
    base_date = datetime.now(UTC)
    for i in range(1, count + 1):
        amount = installment_amount + (remainder if i == count else Decimal("0"))
        inst = RepaymentInstallment(
            contract_id=contract.id,
            installment_number=i,
            due_date=base_date + timedelta(days=30 * i),
            amount=amount,
            status=InstallmentStatus.SCHEDULED,
        )
        db.add(inst)
        installments.append(inst)

    db.flush()
    application.current_phase = TransactionPhase.PHASE_4_REPAYMENT

    log_shariah_step(
        db,
        step_id=ShariahStepId.REPAYMENT_SCHEDULED,
        entity_type="murabaha_contract",
        entity_id=contract.id,
        actor_from=application.institution.name,
        actor_to=application.customer_ref,
        payload={
            "installment_count": count,
            "total_payable": str(total),
        },
    )
    log_audit(
        db,
        entity_type="murabaha_contract",
        entity_id=contract.id,
        actor=actor,
        action="repayment.schedule_generated",
        details=f"installments={count}",
    )
    dispatch_webhook_event(
        db,
        institution_id=application.institution_id,
        event=WebhookEvent.REPAYMENT_DUE,
        data={"application_id": application.id, "installment_count": count},
    )
    return installments


def collect_repayment(
    db: Session,
    installment_id: str,
    payment_ref: str | None = None,
    actor: AuditActor = AuditActor.CUSTOMER,
) -> RepaymentInstallment:
    installment = db.get(RepaymentInstallment, installment_id)
    if not installment:
        raise ValueError("Installment not found")
    if installment.status == InstallmentStatus.PAID:
        return installment

    installment.status = InstallmentStatus.PAID
    installment.paid_at = datetime.now(UTC)
    installment.payment_ref = payment_ref if payment_ref else f"PAY-{uuid.uuid4().hex[:12].upper()}"
    db.flush()

    contract = installment.contract
    application = contract.application if contract else None

    log_shariah_step(
        db,
        step_id=ShariahStepId.REPAYMENT_COLLECTED,
        entity_type="repayment_installment",
        entity_id=installment.id,
        actor_from=application.customer_ref if application else "customer",
        actor_to=application.institution.name if application else "institution",
        payload={
            "installment_number": installment.installment_number,
            "amount": str(installment.amount),
            "payment_ref": installment.payment_ref,
        },
        asset_ref_no=installment.payment_ref,
    )
    log_audit(
        db,
        entity_type="repayment_installment",
        entity_id=installment.id,
        actor=actor,
        action="repayment.received",
        evidence_ref=installment.payment_ref,
    )

    if application and application.customer_id:
        from tawarruq.services import mobile_inbox_service

        mobile_inbox_service.notify_account_by_customer(
            db,
            application.customer_id,
            kind="repayment",
            title="Repayment received",
            body=f"Installment #{installment.installment_number} of KES {installment.amount} is paid.",
            application_id=application.id,
        )

    if application and contract:
        unpaid = [i for i in contract.installments if i.status != InstallmentStatus.PAID.value]
        if not unpaid:
            application.status = ApplicationStatus.COMPLETED
            application.current_phase = TransactionPhase.COMPLETED
            dispatch_webhook_event(
                db,
                institution_id=application.institution_id,
                event=WebhookEvent.REPAYMENT_RECEIVED,
                data={"application_id": application.id, "final": True},
            )
            return installment
        else:
            dispatch_webhook_event(
                db,
                institution_id=application.institution_id,
                event=WebhookEvent.REPAYMENT_RECEIVED,
                data={"application_id": application.id, "installment_id": installment.id},
            )

    return installment
