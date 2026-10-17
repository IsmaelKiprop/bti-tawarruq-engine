from decimal import Decimal

from sqlalchemy.orm import Session

from tawarruq.enums import AmlStatus, ApplicationStatus, AuditActor, KycStatus, ShariahStepId, WebhookEvent
from tawarruq.models.application import FinancingApplication
from tawarruq.models.customer import Customer, LiquidityPool
from tawarruq.services.audit_service import log_audit
from tawarruq.services.shariah_audit_service import log_shariah_step
from tawarruq.services.webhook_service import dispatch_webhook_event

MIN_CREDIT_SCORE = 500
MIN_POOL_RESERVE = Decimal("0")


def ensure_liquidity_pool(db: Session, institution_id: str, initial_amount: Decimal = Decimal("50000000")) -> LiquidityPool:
    pool = db.query(LiquidityPool).filter(LiquidityPool.institution_id == institution_id).first()
    if pool:
        return pool
    pool = LiquidityPool(institution_id=institution_id, available_amount=initial_amount)
    db.add(pool)
    db.flush()
    return pool


def run_eligibility_check(
    db: Session,
    application_id: str,
    *,
    actor: AuditActor = AuditActor.SYSTEM,
) -> FinancingApplication:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")
    if not application.customer_id:
        raise ValueError("Application has no linked customer — register customer first")

    customer = db.get(Customer, application.customer_id)
    if not customer:
        raise ValueError("Customer not found")

    application.status = ApplicationStatus.ELIGIBILITY_PENDING
    db.flush()

    reasons: list[str] = []
    if customer.kyc_status != KycStatus.VERIFIED:
        reasons.append(f"KYC status is {customer.kyc_status}")
    if customer.aml_status not in (AmlStatus.CLEAR,):
        reasons.append(f"AML status is {customer.aml_status}")
    if customer.credit_score < MIN_CREDIT_SCORE:
        reasons.append(f"Credit score {customer.credit_score} below minimum {MIN_CREDIT_SCORE}")

    pool = ensure_liquidity_pool(db, application.institution_id)
    amount = Decimal(str(application.amount_requested))
    if Decimal(str(pool.available_amount)) - Decimal(str(pool.reserved_amount)) < amount:
        reasons.append("Insufficient liquidity pool capacity")

    payload = {
        "application_id": application.id,
        "customer_id": customer.id,
        "kyc_status": customer.kyc_status,
        "aml_status": customer.aml_status,
        "credit_score": customer.credit_score,
        "amount_requested": str(amount),
        "pool_available": str(pool.available_amount),
    }

    if reasons:
        application.status = ApplicationStatus.ELIGIBILITY_FAILED
        application.eligibility_passed = False
        log_shariah_step(
            db,
            step_id=ShariahStepId.ELIGIBILITY_CHECK,
            entity_type="financing_application",
            entity_id=application.id,
            actor_from="system",
            actor_to=customer.full_name,
            payload={**payload, "passed": False, "reasons": reasons},
            details="; ".join(reasons),
        )
        dispatch_webhook_event(
            db,
            institution_id=application.institution_id,
            event=WebhookEvent.ELIGIBILITY_FAILED,
            data={"application_id": application.id, "reasons": reasons},
        )
    else:
        pool.reserved_amount = Decimal(str(pool.reserved_amount)) + amount
        application.status = ApplicationStatus.DRAFT
        application.eligibility_passed = True
        log_shariah_step(
            db,
            step_id=ShariahStepId.ELIGIBILITY_CHECK,
            entity_type="financing_application",
            entity_id=application.id,
            actor_from="system",
            actor_to=customer.full_name,
            payload={**payload, "passed": True},
        )
        dispatch_webhook_event(
            db,
            institution_id=application.institution_id,
            event=WebhookEvent.ELIGIBILITY_PASSED,
            data={"application_id": application.id, "customer_id": customer.id},
        )

    log_audit(
        db,
        entity_type="financing_application",
        entity_id=application.id,
        actor=actor,
        action="eligibility.checked",
        details="passed" if application.eligibility_passed else "; ".join(reasons),
    )
    db.flush()
    return application


def record_institution_eligibility_decision(
    db: Session,
    application_id: str,
    *,
    passed: bool,
    kyc_status: str | None = None,
    aml_status: str | None = None,
    credit_score: int | None = None,
    decision_ref: str | None = None,
    notes: str | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> FinancingApplication:
    """Record the bank or SACCO credit decision, then run the Buruuj gate (pool + stored KYC)."""
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")
    if not application.customer_id:
        raise ValueError("Application has no linked customer — register customer first")
    customer = db.get(Customer, application.customer_id)
    if not customer:
        raise ValueError("Customer not found")

    if kyc_status is not None:
        customer.kyc_status = kyc_status
    if aml_status is not None:
        customer.aml_status = aml_status
    if credit_score is not None:
        customer.credit_score = credit_score

    if not passed:
        application.status = ApplicationStatus.ELIGIBILITY_FAILED
        application.eligibility_passed = False
        reason = notes or "Institution declined the facility"
        log_shariah_step(
            db,
            step_id=ShariahStepId.ELIGIBILITY_CHECK,
            entity_type="financing_application",
            entity_id=application.id,
            actor_from=application.institution.name if application.institution else "institution",
            actor_to=customer.full_name,
            payload={
                "source": "institution",
                "passed": False,
                "decision_ref": decision_ref,
                "notes": notes,
                "kyc_status": customer.kyc_status,
                "aml_status": customer.aml_status,
                "credit_score": customer.credit_score,
            },
            details=reason,
        )
        dispatch_webhook_event(
            db,
            institution_id=application.institution_id,
            event=WebhookEvent.ELIGIBILITY_FAILED,
            data={"application_id": application.id, "reasons": [reason], "source": "institution"},
        )
        log_audit(
            db,
            entity_type="financing_application",
            entity_id=application.id,
            actor=actor,
            action="eligibility.institution_declined",
            details=reason,
        )
        db.flush()
        return application

    if customer.kyc_status != KycStatus.VERIFIED:
        customer.kyc_status = KycStatus.VERIFIED
    if customer.aml_status != AmlStatus.CLEAR:
        customer.aml_status = AmlStatus.CLEAR
    if customer.credit_score < MIN_CREDIT_SCORE:
        customer.credit_score = MIN_CREDIT_SCORE

    log_audit(
        db,
        entity_type="financing_application",
        entity_id=application.id,
        actor=actor,
        action="eligibility.institution_approved",
        details=decision_ref or notes or "institution approved",
    )
    return run_eligibility_check(db, application_id, actor=actor)
