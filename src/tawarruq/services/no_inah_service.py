"""No-Inah guardrail — block financier self-liquidation and originating MNO pool buybacks."""

from sqlalchemy.orm import Session

from tawarruq.enums import AuditActor, WebhookEvent
from tawarruq.models.application import FinancingApplication
from tawarruq.models.institution import Institution
from tawarruq.models.kenya_flow import AssetBatch, ThirdPartyBroker
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.audit_service import log_audit
from tawarruq.services.webhook_service import dispatch_webhook_event

# Maps commodity codes to originating MNO platform entity codes (must not be liquidation counterparty)
ORIGINATING_MNO_ENTITY: dict[str, str] = {
    "AIRTIME_SAFARICOM": "SAFARICOM_MNO",
    "FLOAT_SAFARICOM": "SAFARICOM_MNO",
    "FLOAT_MPESA_DEALER": "SAFARICOM_MNO",
    "AIRTIME_AIRTEL": "AIRTEL_MNO",
    "FLOAT_AIRTEL": "AIRTEL_MNO",
}


def originating_mno_entity(commodity_code: str | None) -> str | None:
    if not commodity_code:
        return None
    if commodity_code in ORIGINATING_MNO_ENTITY:
        return ORIGINATING_MNO_ENTITY[commodity_code]
    for key, entity in ORIGINATING_MNO_ENTITY.items():
        if key in commodity_code:
            return entity
    return None


def _block(
    db: Session,
    transaction: CommodityTransaction,
    *,
    reason: str,
    details: str,
    actor: AuditActor,
) -> None:
    log_audit(
        db,
        entity_type="commodity_transaction",
        entity_id=transaction.id,
        actor=actor,
        action="no_inah.blocked",
        details=details,
    )
    dispatch_webhook_event(
        db,
        institution_id=transaction.institution_id,
        event=WebhookEvent.NO_INAH_BLOCKED,
        data={"transaction_id": transaction.id, "reason": reason, "details": details},
    )


def validate_no_inah(
    db: Session,
    transaction: CommodityTransaction,
    *,
    broker: ThirdPartyBroker,
    actor: AuditActor = AuditActor.SYSTEM,
) -> bool:
    """
    No-Inah guardrail: liquidation must route through an independent third-party broker.
    Blocks:
    - Financier / institution self-liquidation
    - Sale back to the originating MNO platform pool
    - Sale back to the originating Agent Dealer (Dealer A)
    - Non-independent agency brokers
    """
    application = db.get(FinancingApplication, transaction.application_id)
    if not application:
        return False

    institution = db.get(Institution, application.institution_id)
    if institution and broker.code == institution.code:
        _block(db, transaction, reason="financier_self_liquidation", details=f"broker={broker.code}", actor=actor)
        return False

    if institution and broker.id == institution.id:
        _block(db, transaction, reason="financier_self_liquidation", details=f"broker_id={broker.id}", actor=actor)
        return False

    mno_entity = originating_mno_entity(transaction.commodity_code or transaction.mno_code)
    if mno_entity and broker.code == mno_entity:
        _block(
            db,
            transaction,
            reason="originating_mno_pool",
            details=f"broker={broker.code} matches MNO entity {mno_entity}",
            actor=actor,
        )
        return False

    purchase_leg = next((leg for leg in transaction.legs if str(leg.leg_number) == "1"), None)
    source_batch = None
    if purchase_leg:
        source_batch = (
            db.query(AssetBatch).filter(AssetBatch.leg_id == purchase_leg.id).first()
        )
    source_dealer = source_batch.source_dealer_code if source_batch else None
    if source_dealer and broker.code == source_dealer:
        _block(
            db,
            transaction,
            reason="originating_dealer_buyback",
            details=f"broker {broker.code} is the same Dealer A that supplied the float",
            actor=actor,
        )
        return False

    if broker.is_mno_pool:
        _block(
            db,
            transaction,
            reason="mno_platform_pool",
            details=f"broker {broker.code} flagged as MNO pool counterparty",
            actor=actor,
        )
        return False

    commodity = transaction.commodity_code or transaction.mno_code or ""
    if commodity and broker.code == commodity:
        _block(
            db,
            transaction,
            reason="same_commodity_counterparty",
            details=f"broker code equals commodity {commodity}",
            actor=actor,
        )
        return False

    agency = application.customer_agency
    if agency and agency.broker_id == broker.id and not agency.is_independent_liquidator:
        _block(
            db,
            transaction,
            reason="non_independent_agency",
            details=f"broker {broker.code} is not independent liquidator",
            actor=actor,
        )
        return False

    return True


def seed_default_brokers(db: Session) -> None:
    """Seed independent OTC broker and MNO pool entities (blocked by No-Inah)."""
    defaults = [
        ("OTC_KENYA", "Kenya OTC Commodity Desk", "AIRTIME_SAFARICOM,FLOAT_SAFARICOM,FLOAT_MPESA_DEALER,AIRTIME_AIRTEL,FLOAT_AIRTEL", False),
        ("SAFARICOM_MNO", "Safaricom MNO Pool", "AIRTIME_SAFARICOM,FLOAT_SAFARICOM,FLOAT_MPESA_DEALER", True),
        ("AIRTEL_MNO", "Airtel MNO Pool", "AIRTIME_AIRTEL,FLOAT_AIRTEL", True),
    ]
    for code, name, mno_codes, is_mno_pool in defaults:
        existing = db.query(ThirdPartyBroker).filter(ThirdPartyBroker.code == code).first()
        if existing:
            existing.name = name
            existing.mno_codes = mno_codes
            existing.is_mno_pool = is_mno_pool
            existing.active = True
        else:
            db.add(
                ThirdPartyBroker(
                    code=code,
                    name=name,
                    mno_codes=mno_codes,
                    is_mno_pool=is_mno_pool,
                    active=True,
                )
            )
    db.flush()


def select_broker_for_commodity(db: Session, commodity_code: str) -> ThirdPartyBroker | None:
    """Pick an active independent broker for the commodity (never MNO pool)."""
    brokers = (
        db.query(ThirdPartyBroker)
        .filter(ThirdPartyBroker.active.is_(True), ThirdPartyBroker.is_mno_pool.is_(False))
        .all()
    )
    for broker in brokers:
        supported = {code.strip() for code in broker.mno_codes.split(",") if code.strip()}
        if commodity_code in supported or any(code in commodity_code for code in supported):
            return broker
    return brokers[0] if brokers else None
