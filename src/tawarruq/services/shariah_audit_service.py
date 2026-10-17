from sqlalchemy.orm import Session, joinedload

from tawarruq.enums import ShariahStepId
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.kenya_flow import MurabahaContract, ShariahAuditLog
from tawarruq.models.transaction import CommodityTransaction, TransactionLeg
from tawarruq.services.shariah_crypto import compute_payload_hash
from tawarruq.services.shariah_ledger_service import append_shariah_entry, verify_ledger_chain
from tawarruq.services.shariah_audit_remote import mirror_shariah_entry_if_configured


def log_shariah_step(
    db: Session,
    *,
    step_id: ShariahStepId | str,
    entity_type: str,
    entity_id: str,
    actor_from: str,
    actor_to: str,
    payload: dict,
    asset_ref_no: str | None = None,
    details: str | None = None,
    verified_at=None,
    mno_receipt_id: str | None = None,
    institution_id: str | None = None,
    transaction_id: str | None = None,
    application_id: str | None = None,
) -> ShariahAuditLog:
    """Append an immutable Shariah audit entry via the isolated ledger service."""
    entry = append_shariah_entry(
        db,
        step_id=step_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_from=actor_from,
        actor_to=actor_to,
        payload=payload,
        asset_ref_no=asset_ref_no,
        details=details,
        verified_at=verified_at,
        mno_receipt_id=mno_receipt_id,
        institution_id=institution_id,
        transaction_id=transaction_id,
        application_id=application_id,
    )
    mirror_shariah_entry_if_configured(entry, payload)
    return entry


def query_shariah_audit(
    db: Session,
    *,
    entity_id: str | None = None,
    step_id: str | None = None,
    limit: int = 500,
) -> list[ShariahAuditLog]:
    query = db.query(ShariahAuditLog).order_by(ShariahAuditLog.timestamp.desc())
    if entity_id:
        query = query.filter(ShariahAuditLog.entity_id == entity_id)
    if step_id:
        query = query.filter(ShariahAuditLog.step_id == step_id)
    return query.limit(limit).all()


def query_shariah_audit_for_application(db: Session, application_id: str, *, limit: int = 500) -> list[ShariahAuditLog]:
    """Collect Shariah audit entries for an application and its linked entities."""
    from tawarruq.models.application import FinancingApplication

    entity_ids = {application_id}
    application = (
        db.query(FinancingApplication)
        .options(
            joinedload(FinancingApplication.murabaha_contract).joinedload(MurabahaContract.installments),
            joinedload(FinancingApplication.transactions).joinedload(CommodityTransaction.legs).joinedload(
                TransactionLeg.asset_batch
            ),
            joinedload(FinancingApplication.transactions).joinedload(CommodityTransaction.liquidation_order),
            joinedload(FinancingApplication.disbursements).joinedload(Disbursement.wallet_disbursement),
        )
        .filter(FinancingApplication.id == application_id)
        .first()
    )
    if not application:
        return []

    if application.murabaha_contract:
        entity_ids.add(application.murabaha_contract.id)
        for inst in application.murabaha_contract.installments:
            entity_ids.add(inst.id)

    for txn in application.transactions:
        entity_ids.add(txn.id)
        for leg in txn.legs:
            entity_ids.add(leg.id)
            if leg.asset_batch:
                entity_ids.add(leg.asset_batch.id)
        if txn.liquidation_order:
            entity_ids.add(txn.liquidation_order.id)

    for disb in application.disbursements:
        entity_ids.add(disb.id)
        if disb.wallet_disbursement:
            entity_ids.add(disb.wallet_disbursement.id)

    by_entity = (
        db.query(ShariahAuditLog)
        .filter(ShariahAuditLog.entity_id.in_(entity_ids))
        .order_by(ShariahAuditLog.timestamp.asc())
        .limit(limit)
        .all()
    )
    by_application = (
        db.query(ShariahAuditLog)
        .filter(ShariahAuditLog.application_id == application_id)
        .order_by(ShariahAuditLog.timestamp.asc())
        .limit(limit)
        .all()
    )
    merged = {entry.id: entry for entry in by_entity + by_application}
    return sorted(merged.values(), key=lambda e: (e.timestamp, e.id))[:limit]


def verify_application_shariah_integrity(db: Session, application_id: str) -> dict:
    """Regulatory verification: hash chain + possession seal for the application."""
    from tawarruq.models.application import FinancingApplication
    from tawarruq.services.shariah_state_machine import possession_is_cryptographically_sealed

    application = db.get(FinancingApplication, application_id)
    if not application:
        return {"valid": False, "reason": "application not found"}

    chain = verify_ledger_chain(db)
    entries = query_shariah_audit_for_application(db, application_id)
    possession_ok = True
    for txn in application.transactions:
        if txn.mode == "mno" and not possession_is_cryptographically_sealed(db, txn):
            possession_ok = False
            break

    return {
        "valid": chain["valid"] and possession_ok and len(entries) > 0,
        "ledger_chain": chain,
        "possession_sealed": possession_ok,
        "entry_count": len(entries),
        "application_id": application_id,
    }


def export_shariah_ledger(
    db: Session,
    *,
    institution_id: str | None = None,
    application_id: str | None = None,
    limit: int = 10_000,
) -> list[dict]:
    """Regulatory export — ordered append-only ledger rows."""
    query = db.query(ShariahAuditLog).order_by(ShariahAuditLog.timestamp.asc(), ShariahAuditLog.id.asc())
    if institution_id:
        query = query.filter(ShariahAuditLog.institution_id == institution_id)
    if application_id:
        query = query.filter(ShariahAuditLog.application_id == application_id)
    entries = query.limit(limit).all()
    return [
        {
            "id": entry.id,
            "timestamp": entry.timestamp.isoformat(),
            "step_id": entry.step_id,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "asset_ref_no": entry.asset_ref_no,
            "actor_from": entry.actor_from,
            "actor_to": entry.actor_to,
            "payload_hash": entry.payload_hash,
            "details": entry.details,
            "verified_at": entry.verified_at.isoformat() if entry.verified_at else None,
            "mno_receipt_id": entry.mno_receipt_id,
            "institution_id": entry.institution_id,
            "transaction_id": entry.transaction_id,
            "application_id": entry.application_id,
            "previous_hash": entry.previous_hash,
            "entry_hash": entry.entry_hash,
        }
        for entry in entries
    ]
