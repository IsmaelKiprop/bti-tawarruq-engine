from decimal import Decimal

from sqlalchemy.orm import Session

from tawarruq.enums import AmlStatus, AuditActor, KycStatus, ShariahStepId
from tawarruq.models.customer import Customer
from tawarruq.models.institution import Institution
from tawarruq.schemas.kenya import CustomerRead
from tawarruq.services.audit_service import log_audit
from tawarruq.services.shariah_audit_service import log_shariah_step


def to_customer_read(customer: Customer) -> CustomerRead:
    institution = customer.institution
    return CustomerRead(
        id=customer.id,
        institution_id=customer.institution_id,
        institution_name=institution.name if institution else None,
        institution_code=institution.code if institution else None,
        phone=customer.phone,
        email=customer.email,
        full_name=customer.full_name,
        national_id=customer.national_id,
        kyc_status=customer.kyc_status,
        aml_status=customer.aml_status,
        credit_score=customer.credit_score,
        wallet_provider=customer.wallet_provider,
        wallet_number=customer.wallet_number,
        created_at=customer.created_at,
    )


def create_customer(
    db: Session,
    institution_id: str,
    phone: str,
    full_name: str,
    wallet_number: str,
    *,
    email: str | None = None,
    national_id: str | None = None,
    kyc_status: KycStatus = KycStatus.VERIFIED,
    aml_status: AmlStatus = AmlStatus.CLEAR,
    credit_score: int = 650,
    wallet_provider: str = "mpesa",
    actor: AuditActor = AuditActor.HUMAN,
) -> Customer:
    institution = db.get(Institution, institution_id)
    if not institution:
        raise ValueError(f"Institution {institution_id} not found")

    existing = (
        db.query(Customer)
        .filter(Customer.institution_id == institution_id, Customer.phone == phone)
        .first()
    )
    if existing:
        raise ValueError(f"Customer with phone {phone} already exists for this institution")

    from tawarruq.services.customer_notify_service import normalize_email

    customer = Customer(
        institution_id=institution_id,
        phone=phone,
        email=normalize_email(email),
        full_name=full_name,
        national_id=national_id,
        kyc_status=kyc_status,
        aml_status=aml_status,
        credit_score=credit_score,
        wallet_provider=wallet_provider,
        wallet_number=wallet_number,
    )
    db.add(customer)
    db.flush()

    log_audit(
        db,
        entity_type="customer",
        entity_id=customer.id,
        actor=actor,
        action="customer.created",
        details=f"phone={phone}",
    )
    return customer


def update_customer(
    db: Session,
    customer_id: str,
    *,
    full_name: str | None = None,
    email: str | None = None,
    national_id: str | None = None,
    kyc_status: KycStatus | None = None,
    aml_status: AmlStatus | None = None,
    credit_score: int | None = None,
    wallet_number: str | None = None,
    wallet_provider: str | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> Customer:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise ValueError("Customer not found")

    from tawarruq.services.customer_notify_service import normalize_email

    if full_name is not None:
        customer.full_name = full_name
    if email is not None:
        customer.email = normalize_email(email)
    if national_id is not None:
        customer.national_id = national_id
    if kyc_status is not None:
        customer.kyc_status = kyc_status
    if aml_status is not None:
        customer.aml_status = aml_status
    if credit_score is not None:
        customer.credit_score = credit_score
    if wallet_number is not None:
        customer.wallet_number = wallet_number
    if wallet_provider is not None:
        customer.wallet_provider = wallet_provider

    log_audit(
        db,
        entity_type="customer",
        entity_id=customer.id,
        actor=actor,
        action="customer.updated",
        details=f"kyc={customer.kyc_status} aml={customer.aml_status} score={customer.credit_score}",
    )
    db.flush()
    return customer


def delete_customer(
    db: Session,
    customer: Customer,
    *,
    actor: AuditActor = AuditActor.HUMAN,
) -> None:
    from tawarruq.models.application import FinancingApplication
    from tawarruq.services.application_service import delete_application

    customer_id = customer.id
    full_name = customer.full_name
    phone = customer.phone

    applications = db.query(FinancingApplication).filter(FinancingApplication.customer_id == customer_id).all()
    for application in applications:
        delete_application(db, application, actor=actor)

    log_audit(
        db,
        entity_type="customer",
        entity_id=customer_id,
        actor=actor,
        action="customer.deleted",
        details=f"name={full_name}, phone={phone}",
    )
    db.delete(customer)
    db.flush()


def link_customer_to_application(
    db: Session,
    application_id: str,
    customer_id: str,
) -> None:
    from tawarruq.models.application import FinancingApplication

    application = db.get(FinancingApplication, application_id)
    customer = db.get(Customer, customer_id)
    if not application or not customer:
        raise ValueError("Application or customer not found")
    if application.institution_id != customer.institution_id:
        raise ValueError("Customer belongs to a different institution")

    application.customer_id = customer.id
    stored_name = (application.customer_name or "").strip()
    if customer.full_name and (not stored_name or stored_name.upper().startswith("CUST-")):
        application.customer_name = customer.full_name.strip()

    log_shariah_step(
        db,
        step_id=ShariahStepId.FINANCING_REQUEST,
        entity_type="financing_application",
        entity_id=application.id,
        actor_from=customer.full_name,
        actor_to=application.institution.name,
        payload={
            "customer_id": customer.id,
            "amount_requested": str(application.amount_requested),
            "purpose": application.purpose,
        },
        asset_ref_no=application.customer_ref,
    )
    db.flush()
