import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from tawarruq.enums import AgencyStatus, AuditActor, ShariahStepId, WebhookEvent
from tawarruq.models.application import FinancingApplication
from tawarruq.models.business import CustomerAgency, CustomerSale, HumanHandoff, TawarruqFinancingCertificate
from tawarruq.models.disbursement import Disbursement
from tawarruq.services.audit_service import log_audit
from tawarruq.services.no_inah_service import select_broker_for_commodity
from tawarruq.services.shariah_audit_service import log_shariah_step
from tawarruq.services.webhook_service import dispatch_webhook_event


def record_customer_sale(db: Session, application_id: str, *, actor: AuditActor = AuditActor.HUMAN) -> CustomerSale:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")
    if not application.offer:
        raise ValueError("Application has no offer")
    existing = db.query(CustomerSale).filter(CustomerSale.application_id == application_id).first()
    if existing:
        raise ValueError("Customer sale already recorded")

    offer = application.offer
    sale = CustomerSale(
        application_id=application.id,
        cost_price=offer.cost_price,
        profit_amount=offer.profit_amount,
        total_payable=offer.total_payable,
    )
    db.add(sale)
    db.flush()
    log_audit(
        db,
        entity_type="customer_sale",
        entity_id=sale.id,
        actor=actor,
        action="customer_sale.recorded",
        details=f"total_payable={offer.total_payable}",
    )
    dispatch_webhook_event(
        db,
        institution_id=application.institution_id,
        event=WebhookEvent.CUSTOMER_SALE_RECORDED,
        data={"application_id": application.id, "sale_id": sale.id, "total_payable": str(offer.total_payable)},
    )
    return sale


def appoint_customer_agency(
    db: Session,
    application_id: str,
    *,
    notes: str | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> CustomerAgency:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")
    sale = db.query(CustomerSale).filter(CustomerSale.application_id == application_id).first()
    if not sale:
        raise ValueError("Customer sale must be recorded before appointing agency (step 7 before step 8)")
    existing = db.query(CustomerAgency).filter(CustomerAgency.application_id == application_id).first()
    if existing:
        raise ValueError("Customer agency already appointed")

    agency = CustomerAgency(
        application_id=application.id,
        agent_institution_id=application.institution_id,
        status=AgencyStatus.ACTIVE,
        notes=notes,
    )
    db.add(agency)
    db.flush()
    log_audit(
        db,
        entity_type="customer_agency",
        entity_id=agency.id,
        actor=actor,
        action="customer_agency.appointed",
        details=notes,
    )
    dispatch_webhook_event(
        db,
        institution_id=application.institution_id,
        event=WebhookEvent.CUSTOMER_AGENCY_APPOINTED,
        data={"application_id": application.id, "agency_id": agency.id},
    )
    return agency


def appoint_wakala_with_customer_consent(
    db: Session,
    application_id: str,
    *,
    consent_ref: str,
    notes: str | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> CustomerAgency:
    """
    Step 8: Customer appoints platform as Wakala agent to sell commodity to third party.
    Requires Murabaha signed and ownership transfer (customer sale recorded).
    """
    application = (
        db.query(FinancingApplication)
        .options(joinedload(FinancingApplication.transactions), joinedload(FinancingApplication.murabaha_contract))
        .filter(FinancingApplication.id == application_id)
        .first()
    )
    if not application:
        raise ValueError(f"Application {application_id} not found")
    if not application.murabaha_contract or not application.murabaha_contract.signed_at:
        raise ValueError("Murabaha contract must be signed before Wakala appointment")
    sale = db.query(CustomerSale).filter(CustomerSale.application_id == application_id).first()
    if not sale:
        raise ValueError("Ownership transfer must complete before Wakala appointment")

    existing = db.query(CustomerAgency).filter(CustomerAgency.application_id == application_id).first()
    if existing:
        return existing

    txn = application.transactions[-1] if application.transactions else None
    commodity = txn.commodity_code if txn else "AIRTIME_SAFARICOM"
    broker = select_broker_for_commodity(db, commodity)

    agency = CustomerAgency(
        application_id=application.id,
        agent_institution_id=application.institution_id,
        broker_id=broker.id if broker else None,
        is_independent_liquidator=True,
        status=AgencyStatus.ACTIVE,
        notes=notes or f"Customer Wakala consent ref={consent_ref}",
    )
    db.add(agency)
    db.flush()

    log_shariah_step(
        db,
        step_id=ShariahStepId.WAKALA_APPOINTMENT,
        entity_type="customer_agency",
        entity_id=agency.id,
        actor_from=application.customer_ref,
        actor_to=application.institution.name,
        payload={
            "consent_ref": consent_ref,
            "broker_id": agency.broker_id,
            "broker_code": broker.code if broker else None,
        },
        institution_id=application.institution_id,
        transaction_id=txn.id if txn else None,
        application_id=application.id,
    )
    log_audit(
        db,
        entity_type="customer_agency",
        entity_id=agency.id,
        actor=actor,
        action="customer_agency.wakala_consent",
        evidence_ref=consent_ref,
        details=agency.notes,
    )
    dispatch_webhook_event(
        db,
        institution_id=application.institution_id,
        event=WebhookEvent.CUSTOMER_AGENCY_APPOINTED,
        data={"application_id": application.id, "agency_id": agency.id, "consent_ref": consent_ref},
    )
    return agency


def issue_tawarruq_certificate(db: Session, disbursement: Disbursement, *, actor: AuditActor = AuditActor.SYSTEM) -> TawarruqFinancingCertificate:
    if disbursement.tawarruq_certificate:
        return disbursement.tawarruq_certificate

    cert_number = f"TWR-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    cert = TawarruqFinancingCertificate(
        application_id=disbursement.application_id,
        disbursement_id=disbursement.id,
        certificate_number=cert_number,
    )
    db.add(cert)
    db.flush()
    log_audit(
        db,
        entity_type="tawarruq_certificate",
        entity_id=cert.id,
        actor=actor,
        action="tawarruq_certificate.issued",
        evidence_ref=cert_number,
    )
    application = db.get(FinancingApplication, disbursement.application_id)
    if application:
        dispatch_webhook_event(
            db,
            institution_id=application.institution_id,
            event=WebhookEvent.TAWARRUQ_CERTIFICATE_ISSUED,
            data={
                "application_id": disbursement.application_id,
                "disbursement_id": disbursement.id,
                "certificate_number": cert_number,
            },
        )
    return cert


def record_handoff(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    reason: str,
    assigned_to: str | None = None,
    channel: str | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> HumanHandoff:
    handoff = HumanHandoff(
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        assigned_to=assigned_to,
        channel=channel,
    )
    db.add(handoff)
    db.flush()
    log_audit(
        db,
        entity_type="human_handoff",
        entity_id=handoff.id,
        actor=actor,
        action="handoff.recorded",
        details=f"{entity_type}:{entity_id} reason={reason}",
    )
    return handoff


def business_steps_ready_for_leg3(db: Session, application_id: str) -> bool:
    sale = db.query(CustomerSale).filter(CustomerSale.application_id == application_id).first()
    agency = db.query(CustomerAgency).filter(CustomerAgency.application_id == application_id).first()
    return sale is not None and agency is not None
