"""Ordered Malaysia Tawarruq runner for mock E2E and partner-desk dry runs."""

from sqlalchemy.orm import Session, joinedload

from tawarruq.amanah.worker import AmanahWorker
from tawarruq.enums import ApplicationStatus, AuditActor, TransactionMode, TransactionStatus
from tawarruq.models.application import FinancingApplication
from tawarruq.models.business import TawarruqFinancingCertificate
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.transaction_service import create_disbursement, create_transaction, get_transaction_detail


def _malaysia_transaction(db: Session, application_id: str) -> CommodityTransaction | None:
    return (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.legs))
        .filter(
            CommodityTransaction.application_id == application_id,
            CommodityTransaction.mode.in_(
                {TransactionMode.MOCK, TransactionMode.MANUAL_BRIDGE, TransactionMode.LIVE, "mock", "manual_bridge", "live"}
            ),
        )
        .order_by(CommodityTransaction.created_at.desc())
        .first()
    )


def run_ordered_malaysia_flow(db: Session, application_id: str) -> dict:
    """Run mock Malaysia 3-leg flow + business steps + disbursement.

    Manual-bridge and live modes stay human/partner driven. This runner is the
    Kenya-style one-click path for local and CI end-to-end tests.
    """
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise ValueError("Application not found")
    if application.status not in {ApplicationStatus.OFFER_ACCEPTED, ApplicationStatus.IN_PROGRESS}:
        raise ValueError(f"Application must have an accepted offer, got {application.status}")

    transaction = _malaysia_transaction(db, application_id)
    if not transaction:
        transaction = create_transaction(
            db,
            application_id=application_id,
            commodity_code="PALM_OIL",
            mode=TransactionMode.MOCK,
            actor=AuditActor.AI_WORKER,
        )
        db.flush()

    if transaction.mode not in {TransactionMode.MOCK, "mock"}:
        raise ValueError(
            "run-full-flow is mock-only. For Suq Al-Sila' use manual_bridge (desk packet + e-certificate). "
            "For Eiger or a live desk API, set MALAYSIA_COMMODITY_DESK and LIVE credentials."
        )

    worker = AmanahWorker(write_enabled=True)
    for _ in range(8):
        detail = get_transaction_detail(db, transaction.id)
        if not detail:
            raise ValueError("Transaction disappeared during Malaysia flow")
        if detail.status == TransactionStatus.COMPLETED:
            transaction = detail
            break
        if detail.status in {TransactionStatus.FAILED, TransactionStatus.ESCALATED}:
            raise ValueError(f"Malaysia flow stopped: {detail.status}")
        worker.process_transaction(db, detail)
        db.commit()
    else:
        detail = get_transaction_detail(db, transaction.id)
        raise ValueError(f"Malaysia flow did not complete (status={detail.status if detail else 'missing'})")

    existing = (
        db.query(Disbursement)
        .filter(Disbursement.application_id == application_id, Disbursement.transaction_id == transaction.id)
        .first()
    )
    if not existing:
        disbursement = create_disbursement(
            db,
            application_id=application_id,
            transaction_id=transaction.id,
            actor=AuditActor.AI_WORKER,
        )
        db.flush()
    else:
        disbursement = existing

    cert = (
        db.query(TawarruqFinancingCertificate)
        .filter(TawarruqFinancingCertificate.disbursement_id == disbursement.id)
        .first()
    )
    confirmed = sum(1 for leg in transaction.legs if str(leg.status) == "confirmed")
    return {
        "application_id": application_id,
        "transaction_id": transaction.id,
        "status": str(transaction.status),
        "legs_confirmed": confirmed,
        "disbursement_id": disbursement.id,
        "certificate_number": cert.certificate_number if cert else None,
    }
