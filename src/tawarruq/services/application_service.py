from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from tawarruq.enums import ApplicationStatus, AuditActor, WebhookEvent
from tawarruq.schemas import ApplicationRead
from tawarruq.models.application import FinancingApplication, FinancingOffer
from tawarruq.models.institution import Institution
from tawarruq.services.audit_service import log_audit
from tawarruq.services.malaysia_shariah_service import (
    log_malaysia_acceptance,
    log_malaysia_financing_request,
    log_malaysia_offer,
)
from tawarruq.services.webhook_service import dispatch_webhook_event


def _is_generated_ref(value: str | None) -> bool:
    raw = (value or "").strip().upper()
    return raw.startswith("CUST-")


def display_customer_name(application: FinancingApplication) -> str | None:
    candidates: list[str] = []
    customer = getattr(application, "customer", None)
    if customer is not None and getattr(customer, "full_name", None):
        candidates.append(customer.full_name)
    if application.customer_name:
        candidates.append(application.customer_name)
    for raw in candidates:
        name = raw.strip()
        if name and not _is_generated_ref(name):
            return name
    return None


def to_application_read(application: FinancingApplication) -> ApplicationRead:
    institution = getattr(application, "institution", None)
    return ApplicationRead(
        id=application.id,
        institution_id=application.institution_id,
        institution_name=institution.name if institution is not None else None,
        customer_id=application.customer_id,
        customer_ref=application.customer_ref,
        customer_name=display_customer_name(application),
        currency=application.currency or "KES",
        amount_requested=application.amount_requested,
        term_months=application.term_months,
        purpose=application.purpose,
        status=application.status,
        current_phase=application.current_phase,
        wad_accepted_at=application.wad_accepted_at,
        created_at=application.created_at,
        updated_at=application.updated_at,
    )


def generate_customer_ref(db: Session, institution: Institution) -> str:
    """Generate institution-scoped customer reference: CUST-{CODE}-{YYYY}-{NNNN}."""
    year = datetime.now(UTC).strftime("%Y")
    prefix = f"CUST-{institution.code}-{year}-"
    count = (
        db.query(func.count(FinancingApplication.id))
        .filter(
            FinancingApplication.institution_id == institution.id,
            FinancingApplication.customer_ref.like(f"{prefix}%"),
        )
        .scalar()
    ) or 0
    return f"{prefix}{count + 1:04d}"


def get_or_create_default_institution(db: Session) -> Institution:
    from tawarruq.config import get_settings

    settings = get_settings()
    if settings.is_onprem:
        code = (settings.onprem_institution_code or "SITE").strip().upper() or "SITE"
        name = (settings.onprem_institution_name or settings.brand_display).strip() or settings.brand_display
        institution = db.query(Institution).filter(Institution.code == code).first()
        if institution:
            return institution
        default = db.query(Institution).filter(Institution.code == "DEFAULT").first()
        if default:
            return default
        institution = Institution(name=name, code=code, bsas_mode="mock")
        db.add(institution)
        db.flush()
        log_audit(
            db,
            entity_type="institution",
            entity_id=institution.id,
            actor=AuditActor.SYSTEM,
            action="institution.created",
            details="On-prem site institution seeded",
        )
        return institution

    institution = db.query(Institution).filter(Institution.code == "DEFAULT").first()
    if institution:
        if (institution.name or "").strip() in {"", "Default Institution"}:
            institution.name = "Demo Partner SACCO"
            db.flush()
        return institution
    institution = Institution(name="Demo Partner SACCO", code="DEFAULT", bsas_mode="mock")
    db.add(institution)
    db.flush()
    log_audit(
        db,
        entity_type="institution",
        entity_id=institution.id,
        actor=AuditActor.SYSTEM,
        action="institution.created",
        details="Default lending institution seeded",
    )
    return institution


def resolve_institution(
    db: Session, *, institution_id: str | None, institution_code: str | None
) -> Institution:
    if institution_id:
        institution = db.get(Institution, institution_id)
        if not institution:
            raise ValueError(f"Institution {institution_id} not found")
        return institution
    if institution_code:
        institution = db.query(Institution).filter(Institution.code == institution_code).first()
        if not institution:
            raise ValueError(f"Institution code {institution_code} not found")
        return institution
    return get_or_create_default_institution(db)


def create_application(
    db: Session,
    *,
    customer_ref: str | None = None,
    customer_name: str | None = None,
    customer_id: str | None = None,
    currency: str = "KES",
    amount_requested: Decimal,
    term_months: int,
    purpose: str,
    institution_id: str | None = None,
    institution_code: str | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> FinancingApplication:
    from tawarruq.models.customer import Customer
    from tawarruq.services.customer_service import link_customer_to_application

    institution = resolve_institution(db, institution_id=institution_id, institution_code=institution_code)
    customer = None
    if customer_id:
        customer = db.get(Customer, customer_id)
        if not customer:
            raise ValueError("Customer not found")
        if customer.institution_id != institution.id:
            raise ValueError("Customer belongs to a different institution")
    resolved_ref = customer_ref.strip() if customer_ref and customer_ref.strip() else generate_customer_ref(db, institution)
    resolved_currency = (currency or "KES").strip().upper() or "KES"
    resolved_name = customer_name.strip() if customer_name and customer_name.strip() else None
    if customer and not resolved_name:
        resolved_name = customer.full_name.strip()
    application = FinancingApplication(
        institution_id=institution.id,
        customer_ref=resolved_ref,
        customer_name=resolved_name,
        currency=resolved_currency,
        amount_requested=amount_requested,
        term_months=term_months,
        purpose=purpose,
        status=ApplicationStatus.DRAFT,
    )
    db.add(application)
    db.flush()
    if customer:
        link_customer_to_application(db, application.id, customer.id)
    db.refresh(application, attribute_names=["institution", "customer"])
    from tawarruq.services.trade_evidence_service import record_purchase_undertaking

    record_purchase_undertaking(db, application)
    log_malaysia_financing_request(db, application)
    log_audit(
        db,
        entity_type="financing_application",
        entity_id=application.id,
        actor=actor,
        action="application.created",
        details=f"amount={amount_requested}, term={term_months}m",
    )
    dispatch_webhook_event(
        db,
        institution_id=institution.id,
        event=WebhookEvent.APPLICATION_CREATED,
        data={"application_id": application.id, "customer_ref": resolved_ref, "status": application.status},
    )
    return application


def create_offer(
    db: Session,
    application_id: str,
    *,
    cost_price: Decimal | None = None,
    profit_rate_pct: Decimal = Decimal("5.0"),
    actor: AuditActor = AuditActor.HUMAN,
) -> FinancingOffer:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")
    if application.offer:
        raise ValueError("Offer already exists for this application")

    resolved_cost = cost_price or Decimal(str(application.amount_requested))
    profit_amount = (resolved_cost * profit_rate_pct / Decimal("100")).quantize(Decimal("0.01"))
    total_payable = resolved_cost + profit_amount

    offer = FinancingOffer(
        application_id=application.id,
        cost_price=resolved_cost,
        profit_amount=profit_amount,
        total_payable=total_payable,
    )
    application.status = ApplicationStatus.OFFER_PENDING
    db.add(offer)
    db.flush()
    db.refresh(application, attribute_names=["institution"])
    log_malaysia_offer(db, application, total_payable=str(total_payable))
    log_audit(
        db,
        entity_type="financing_offer",
        entity_id=offer.id,
        actor=actor,
        action="offer.generated",
        details=f"cost={resolved_cost}, profit={profit_amount}, total={total_payable}",
    )
    dispatch_webhook_event(
        db,
        institution_id=application.institution_id,
        event=WebhookEvent.OFFER_GENERATED,
        data={"application_id": application.id, "offer_id": offer.id, "total_payable": str(total_payable)},
    )
    try:
        from tawarruq.services.customer_notify_service import notify_offer_ready

        db.refresh(application, attribute_names=["customer", "institution", "offer"])
        notify_offer_ready(db, application)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Could not notify customer of locked offer")
    return offer


def accept_offer(db: Session, application_id: str, *, actor: AuditActor = AuditActor.HUMAN) -> FinancingOffer:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")
    if not application.offer:
        raise ValueError("No offer to accept")
    if application.offer.accepted_at:
        raise ValueError("Offer already accepted")

    from datetime import UTC, datetime

    application.offer.accepted_at = datetime.now(UTC)
    application.status = ApplicationStatus.OFFER_ACCEPTED
    db.flush()
    db.refresh(application, attribute_names=["institution"])
    log_malaysia_acceptance(db, application)
    log_audit(
        db,
        entity_type="financing_application",
        entity_id=application.id,
        actor=actor,
        action="offer.accepted",
        details=f"offer_id={application.offer.id}",
    )
    dispatch_webhook_event(
        db,
        institution_id=application.institution_id,
        event=WebhookEvent.OFFER_ACCEPTED,
        data={"application_id": application.id, "offer_id": application.offer.id},
    )
    return application.offer


def delete_application(db: Session, application: FinancingApplication, *, actor: AuditActor = AuditActor.HUMAN) -> None:
    from tawarruq.models.business import CustomerAgency, CustomerSale, TawarruqFinancingCertificate
    from tawarruq.models.certificate import Certificate
    from tawarruq.models.disbursement import Disbursement
    from tawarruq.models.kenya_flow import (
        AssetBatch,
        LiquidationOrder,
        MurabahaContract,
        RepaymentInstallment,
        WalletDisbursement,
    )
    from tawarruq.models.transaction import CommodityTransaction, TransactionLeg

    app_id = application.id
    customer_ref = application.customer_ref

    transactions = db.query(CommodityTransaction).filter(CommodityTransaction.application_id == app_id).all()
    transaction_ids = [item.id for item in transactions]
    disbursements = db.query(Disbursement).filter(Disbursement.application_id == app_id).all()
    disbursement_ids = [item.id for item in disbursements]
    leg_ids = [
        leg.id
        for txn in transactions
        for leg in db.query(TransactionLeg).filter(TransactionLeg.transaction_id == txn.id).all()
    ]

    if disbursement_ids:
        db.query(WalletDisbursement).filter(WalletDisbursement.disbursement_id.in_(disbursement_ids)).delete(
            synchronize_session=False
        )
        db.query(TawarruqFinancingCertificate).filter(
            TawarruqFinancingCertificate.disbursement_id.in_(disbursement_ids)
        ).delete(synchronize_session=False)
        db.query(TawarruqFinancingCertificate).filter(TawarruqFinancingCertificate.application_id == app_id).delete(
            synchronize_session=False
        )
        db.query(Disbursement).filter(Disbursement.id.in_(disbursement_ids)).update(
            {Disbursement.certificate_id: None}, synchronize_session=False
        )
        db.flush()
        db.query(Disbursement).filter(Disbursement.id.in_(disbursement_ids)).delete(synchronize_session=False)

    if transaction_ids:
        db.query(LiquidationOrder).filter(LiquidationOrder.transaction_id.in_(transaction_ids)).delete(
            synchronize_session=False
        )
    if leg_ids:
        db.query(AssetBatch).filter(AssetBatch.leg_id.in_(leg_ids)).delete(synchronize_session=False)
        db.query(Certificate).filter(Certificate.leg_id.in_(leg_ids)).delete(synchronize_session=False)
        db.query(TransactionLeg).filter(TransactionLeg.id.in_(leg_ids)).delete(synchronize_session=False)
    if transaction_ids:
        db.query(CommodityTransaction).filter(CommodityTransaction.id.in_(transaction_ids)).delete(
            synchronize_session=False
        )

    contracts = db.query(MurabahaContract).filter(MurabahaContract.application_id == app_id).all()
    contract_ids = [item.id for item in contracts]
    if contract_ids:
        db.query(RepaymentInstallment).filter(RepaymentInstallment.contract_id.in_(contract_ids)).delete(
            synchronize_session=False
        )
        db.query(MurabahaContract).filter(MurabahaContract.id.in_(contract_ids)).delete(synchronize_session=False)

    db.query(CustomerSale).filter(CustomerSale.application_id == app_id).delete(synchronize_session=False)
    db.query(CustomerAgency).filter(CustomerAgency.application_id == app_id).delete(synchronize_session=False)
    db.query(FinancingOffer).filter(FinancingOffer.application_id == app_id).delete(synchronize_session=False)

    log_audit(
        db,
        entity_type="financing_application",
        entity_id=app_id,
        actor=actor,
        action="application.deleted",
        details=f"customer_ref={customer_ref}",
    )
    db.delete(application)
    db.flush()
