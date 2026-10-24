from tawarruq.enums import AuditActor, TransactionMode
from tawarruq.models.business import CustomerAgency
from tawarruq.models.customer import Customer, LiquidityPool
from tawarruq.models.institution import Institution
from tawarruq.models.institution_integration import InstitutionIntegration
from tawarruq.models.integration import ApiKey, WebhookSubscription
from tawarruq.models.kenya_flow import AgentDealer, AgentDealerFloatTopup
from tawarruq.models.ops_user import OpsUser
from tawarruq.models.application import FinancingApplication
from tawarruq.services.application_service import delete_application
from tawarruq.services.audit_service import log_audit

VALID_BSAS_MODES = {TransactionMode.MOCK, TransactionMode.MANUAL_BRIDGE, TransactionMode.LIVE}
PROTECTED_INSTITUTION_CODE = "DEFAULT"


VALID_APPROVAL_STEPS = {"murabaha", "liquidation", "disbursement"}


def update_institution(
    db,
    institution: Institution,
    *,
    name: str | None = None,
    bsas_mode: str | None = None,
    active: bool | None = None,
    approval_steps: str | None = None,
    approval_limit_amount=None,
    billing_fee_bps: int | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> Institution:
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Institution name is required")
        institution.name = cleaned
    if bsas_mode is not None:
        if bsas_mode not in VALID_BSAS_MODES:
            raise ValueError(f"bsas_mode must be one of: {', '.join(VALID_BSAS_MODES)}")
        institution.bsas_mode = bsas_mode
    if active is not None:
        institution.active = bool(active)
    if approval_steps is not None:
        parts = [part.strip().lower() for part in approval_steps.split(",") if part.strip()]
        unknown = [part for part in parts if part not in VALID_APPROVAL_STEPS]
        if unknown:
            raise ValueError(f"Unknown approval steps: {', '.join(unknown)}")
        institution.approval_steps = ",".join(parts)
    if approval_limit_amount is not None:
        institution.approval_limit_amount = approval_limit_amount if approval_limit_amount != "" else None
    if billing_fee_bps is not None:
        if billing_fee_bps < 0 or billing_fee_bps > 10_000:
            raise ValueError("billing_fee_bps must be between 0 and 10000")
        institution.billing_fee_bps = billing_fee_bps
    log_audit(
        db,
        entity_type="institution",
        entity_id=institution.id,
        actor=actor,
        action="institution.updated",
        details=(
            f"name={institution.name}, mode={institution.bsas_mode}, active={institution.active}, "
            f"steps={institution.approval_steps}"
        ),
        institution_id=institution.id,
        action_group="institutions",
    )
    db.flush()
    return institution


def delete_institution(db, institution: Institution, *, actor: AuditActor = AuditActor.HUMAN) -> None:
    if institution.code.upper() == PROTECTED_INSTITUTION_CODE:
        raise ValueError("The default institution cannot be deleted")

    leftover_agency = (
        db.query(CustomerAgency)
        .join(FinancingApplication, CustomerAgency.application_id == FinancingApplication.id)
        .filter(
            CustomerAgency.agent_institution_id == institution.id,
            FinancingApplication.institution_id != institution.id,
        )
        .count()
    )
    if leftover_agency:
        raise ValueError("This institution is still the selling agent on another bank's deal")

    institution_id = institution.id
    name = institution.name
    code = institution.code

    applications = (
        db.query(FinancingApplication).filter(FinancingApplication.institution_id == institution_id).all()
    )
    for application in applications:
        delete_application(db, application, actor=actor)

    dealers = db.query(AgentDealer).filter(AgentDealer.institution_id == institution_id).all()
    dealer_ids = [item.id for item in dealers]
    if dealer_ids:
        db.query(AgentDealerFloatTopup).filter(AgentDealerFloatTopup.dealer_id.in_(dealer_ids)).delete(
            synchronize_session=False
        )
        db.query(AgentDealer).filter(AgentDealer.id.in_(dealer_ids)).delete(synchronize_session=False)

    db.query(InstitutionIntegration).filter(InstitutionIntegration.institution_id == institution_id).delete(
        synchronize_session=False
    )
    db.query(WebhookSubscription).filter(WebhookSubscription.institution_id == institution_id).delete(
        synchronize_session=False
    )
    db.query(ApiKey).filter(ApiKey.institution_id == institution_id).delete(synchronize_session=False)
    db.query(LiquidityPool).filter(LiquidityPool.institution_id == institution_id).delete(synchronize_session=False)
    db.query(Customer).filter(Customer.institution_id == institution_id).delete(synchronize_session=False)

    from tawarruq.models.controls import BillingInvoice, PendingApproval, ReconciliationItem

    db.query(PendingApproval).filter(PendingApproval.institution_id == institution_id).delete(synchronize_session=False)
    db.query(BillingInvoice).filter(BillingInvoice.institution_id == institution_id).delete(synchronize_session=False)
    db.query(ReconciliationItem).filter(ReconciliationItem.institution_id == institution_id).delete(
        synchronize_session=False
    )

    users = db.query(OpsUser).filter(OpsUser.institution_id == institution_id).all()
    user_ids = [item.id for item in users]
    if user_ids:
        db.query(OpsUser).filter(OpsUser.created_by_id.in_(user_ids)).update(
            {OpsUser.created_by_id: None}, synchronize_session=False
        )
        db.query(OpsUser).filter(OpsUser.id.in_(user_ids)).delete(synchronize_session=False)

    log_audit(
        db,
        entity_type="institution",
        entity_id=institution_id,
        actor=actor,
        action="institution.deleted",
        details=f"code={code}, name={name}",
        institution_id=institution_id,
        action_group="institutions",
    )
    db.delete(institution)
    db.flush()
