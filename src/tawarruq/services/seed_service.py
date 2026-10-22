from sqlalchemy.orm import Session

from tawarruq.models.institution import Institution
from tawarruq.services.customer_service import create_customer
from tawarruq.services.eligibility_service import ensure_liquidity_pool
from tawarruq.services.no_inah_service import seed_default_brokers


def seed_kenya_defaults(db: Session) -> None:
    seed_default_brokers(db)
    _seed_mwalimu_demo(db)
    _seed_sedania_bank_demo(db)
    for institution in db.query(Institution).all():
        ensure_liquidity_pool(db, institution.id)


def _seed_mwalimu_demo(db: Session) -> None:
    from tawarruq.models.customer import Customer

    institution = db.query(Institution).filter(Institution.code == "MWALIMU").first()
    if not institution:
        institution = Institution(name="Mwalimu National SACCO", code="MWALIMU", bsas_mode="mock")
        db.add(institution)
        db.flush()

    existing_customer = (
        db.query(Customer)
        .filter(Customer.institution_id == institution.id, Customer.phone == "254700050000")
        .first()
    )
    if not existing_customer:
        create_customer(
            db,
            institution_id=institution.id,
            phone="254700050000",
            email="hidaya.said@example.com",
            full_name="Hidaya Said",
            wallet_number="254700050000",
            national_id="DEMO-HIDAYA",
            kyc_status="verified",
            aml_status="clear",
            credit_score=680,
        )
    elif not existing_customer.email:
        existing_customer.email = "hidaya.said@example.com"


def _seed_sedania_bank_demo(db: Session) -> None:
    from tawarruq.models.customer import Customer

    institution = db.query(Institution).filter(Institution.code == "DIB").first()
    if not institution:
        institution = Institution(name="Demo Islamic Bank", code="DIB", bsas_mode="mock")
        db.add(institution)
        db.flush()

    existing_customer = (
        db.query(Customer)
        .filter(Customer.institution_id == institution.id, Customer.phone == "60123450001")
        .first()
    )
    if not existing_customer:
        create_customer(
            db,
            institution_id=institution.id,
            phone="60123450001",
            email="amina.rahman@example.com",
            full_name="Amina Rahman",
            wallet_number="CASA-DIB-0001",
            national_id="DEMO-AMINA-RAHMAN",
            kyc_status="verified",
            aml_status="clear",
            credit_score=710,
        )
    elif not existing_customer.email:
        existing_customer.email = "amina.rahman@example.com"
