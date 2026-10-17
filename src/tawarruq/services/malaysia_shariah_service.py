"""Shariah audit hooks for Malaysia BSAS Tawarruq flow."""

from sqlalchemy.orm import Session

from tawarruq.enums import ShariahStepId
from tawarruq.models.application import FinancingApplication
from tawarruq.services.shariah_audit_service import log_shariah_step


def log_malaysia_financing_request(db: Session, application: FinancingApplication) -> None:
    log_shariah_step(
        db,
        step_id=ShariahStepId.FINANCING_REQUEST,
        entity_type="financing_application",
        entity_id=application.id,
        actor_from=application.customer_ref,
        actor_to=application.institution.name,
        payload={
            "amount_requested": str(application.amount_requested),
            "purpose": application.purpose,
            "flow": "malaysia_bsas",
        },
        asset_ref_no=application.customer_ref,
    )


def log_malaysia_offer(db: Session, application: FinancingApplication, *, total_payable: str) -> None:
    log_shariah_step(
        db,
        step_id=ShariahStepId.MURABAHA_OFFER,
        entity_type="financing_application",
        entity_id=application.id,
        actor_from=application.institution.name,
        actor_to=application.customer_ref,
        payload={"total_payable": total_payable, "flow": "malaysia_bsas"},
    )


def log_malaysia_acceptance(db: Session, application: FinancingApplication) -> None:
    log_shariah_step(
        db,
        step_id=ShariahStepId.CUSTOMER_ACCEPTANCE,
        entity_type="financing_application",
        entity_id=application.id,
        actor_from=application.customer_ref,
        actor_to=application.institution.name,
        payload={"flow": "malaysia_bsas"},
    )


def log_malaysia_leg(
    db: Session,
    *,
    transaction_id: str,
    leg_number: str,
    application: FinancingApplication,
    certificate_number: str | None = None,
) -> None:
    step_map = {
        "1": ShariahStepId.MURABAHA_PURCHASE,
        "2": ShariahStepId.OWNERSHIP_TRANSFER,
        "3": ShariahStepId.THIRD_PARTY_LIQUIDATION,
    }
    log_shariah_step(
        db,
        step_id=step_map.get(leg_number, ShariahStepId.MURABAHA_PURCHASE),
        entity_type="commodity_transaction",
        entity_id=transaction_id,
        actor_from=application.institution.name,
        actor_to=application.customer_ref,
        payload={"leg_number": leg_number, "flow": "malaysia_bsas"},
        asset_ref_no=certificate_number,
    )


def log_malaysia_disbursement(
    db: Session,
    *,
    application: FinancingApplication,
    disbursement_id: str,
    amount: str,
    external_ref: str | None = None,
) -> None:
    log_shariah_step(
        db,
        step_id=ShariahStepId.WALLET_DISBURSEMENT,
        entity_type="disbursement",
        entity_id=disbursement_id,
        actor_from=application.institution.name,
        actor_to=application.customer_ref,
        payload={"amount": amount, "flow": "malaysia_bsas"},
        asset_ref_no=external_ref,
    )
