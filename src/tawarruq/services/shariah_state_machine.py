"""Shariah-compliant transaction phase and leg state machine enforcement."""

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from tawarruq.enums import LegNumber, LegStatus, PossessionStatus, ShariahStepId, TransactionPhase
from tawarruq.models.application import FinancingApplication
from tawarruq.models.kenya_flow import AssetBatch, ShariahAuditLog
from tawarruq.models.transaction import CommodityTransaction, TransactionLeg

PHASE_ORDER = (
    TransactionPhase.PHASE_1_PURCHASE,
    TransactionPhase.PHASE_2_MURABAHA,
    TransactionPhase.PHASE_3_LIQUIDATION,
    TransactionPhase.PHASE_4_REPAYMENT,
    TransactionPhase.COMPLETED,
)

ALLOWED_PHASE_TRANSITIONS: dict[str, set[str]] = {
    TransactionPhase.PHASE_1_PURCHASE: {TransactionPhase.PHASE_2_MURABAHA},
    TransactionPhase.PHASE_2_MURABAHA: {TransactionPhase.PHASE_3_LIQUIDATION},
    TransactionPhase.PHASE_3_LIQUIDATION: {TransactionPhase.PHASE_4_REPAYMENT, TransactionPhase.COMPLETED},
    TransactionPhase.PHASE_4_REPAYMENT: {TransactionPhase.COMPLETED},
}


class ShariahStateViolation(Exception):
    """Raised when a transaction attempts to skip a mandatory Shariah phase."""


def _phase_index(phase: str) -> int:
    try:
        return PHASE_ORDER.index(phase)  # type: ignore[arg-type]
    except ValueError:
        return -1


def _get_leg(transaction: CommodityTransaction, leg_number: LegNumber) -> TransactionLeg | None:
    return next((leg for leg in transaction.legs if leg.leg_number == leg_number), None)


def get_possession_batch(db: Session, transaction: CommodityTransaction) -> AssetBatch | None:
    purchase = _get_leg(transaction, LegNumber.PURCHASE)
    if not purchase:
        return None
    if purchase.asset_batch:
        return purchase.asset_batch
    return db.query(AssetBatch).filter(AssetBatch.leg_id == purchase.id).first()


def possession_is_cryptographically_sealed(db: Session, transaction: CommodityTransaction) -> bool:
    """
    Phase 2 (constructive possession) is sealed when:
    - Asset batch is VERIFIED with server timestamp and MNO receipt ID
    - Immutable Shariah audit entry exists for CONSTRUCTIVE_POSSESSION
    """
    batch = get_possession_batch(db, transaction)
    if not batch:
        return False
    if batch.possession_status != PossessionStatus.VERIFIED:
        return False
    if not batch.verified_at or not isinstance(batch.verified_at, datetime):
        return False
    if not batch.mno_receipt_id or not str(batch.mno_receipt_id).strip():
        return False
    if not batch.asset_ref_hash:
        return False

    audit = (
        db.query(ShariahAuditLog)
        .filter(
            ShariahAuditLog.step_id == ShariahStepId.CONSTRUCTIVE_POSSESSION,
            ShariahAuditLog.entity_id == batch.id,
        )
        .first()
    )
    if not audit:
        return False
    if not audit.verified_at:
        return False
    if not audit.mno_receipt_id or audit.mno_receipt_id != batch.mno_receipt_id:
        return False
    return True


def assert_possession_sealed(db: Session, transaction: CommodityTransaction) -> None:
    if possession_is_cryptographically_sealed(db, transaction):
        return
    raise ShariahStateViolation(
        "Constructive possession is not sealed: verified UTC timestamp and MNO receipt ID required "
        "before advancing beyond Phase 2 (Murabaha)."
    )


def validate_phase_transition(
    db: Session,
    transaction: CommodityTransaction,
    new_phase: str,
) -> None:
    current = transaction.phase or TransactionPhase.PHASE_1_PURCHASE
    if new_phase == current:
        return

    allowed = ALLOWED_PHASE_TRANSITIONS.get(current, set())
    if new_phase not in allowed and new_phase != TransactionPhase.COMPLETED:
        raise ShariahStateViolation(f"Invalid phase transition {current} -> {new_phase}")

    current_idx = _phase_index(current)
    new_idx = _phase_index(new_phase)
    if new_idx > current_idx + 1 and new_phase != TransactionPhase.COMPLETED:
        raise ShariahStateViolation(f"Cannot skip phases: {current} -> {new_phase}")

    # Cannot enter Phase 3 (liquidation) or beyond without sealed possession
    if _phase_index(new_phase) >= _phase_index(TransactionPhase.PHASE_3_LIQUIDATION):
        assert_possession_sealed(db, transaction)

    purchase = _get_leg(transaction, LegNumber.PURCHASE)
    if purchase and purchase.status != LegStatus.CONFIRMED and _phase_index(new_phase) > _phase_index(
        TransactionPhase.PHASE_1_PURCHASE
    ):
        raise ShariahStateViolation("Purchase leg must be confirmed before leaving Phase 1")


def validate_liquidation_allowed(db: Session, transaction_id: str) -> CommodityTransaction:
    transaction = (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.legs).joinedload(TransactionLeg.asset_batch))
        .filter(CommodityTransaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise ValueError("Transaction not found")

    current_phase = transaction.phase or TransactionPhase.PHASE_1_PURCHASE
    if _phase_index(current_phase) < _phase_index(TransactionPhase.PHASE_2_MURABAHA):
        raise ShariahStateViolation(
            "Cannot liquidate (Phase 3) while still in Phase 1 — possession must be verified first"
        )

    assert_possession_sealed(db, transaction)

    transfer = _get_leg(transaction, LegNumber.TRANSFER)
    if not transfer or transfer.status != LegStatus.CONFIRMED:
        raise ShariahStateViolation("Ownership transfer (Leg 2) must be confirmed before liquidation")

    application = db.get(FinancingApplication, transaction.application_id)
    if not application or not application.murabaha_contract or not application.murabaha_contract.signed_at:
        raise ShariahStateViolation("Murabaha contract must be signed before liquidation")

    return transaction


def advance_phase(db: Session, transaction: CommodityTransaction, new_phase: str) -> None:
    """Validate and apply a phase transition (state machine enforced)."""
    validate_phase_transition(db, transaction, new_phase)
    transaction.phase = new_phase
    application = db.get(FinancingApplication, transaction.application_id)
    if application:
        application.current_phase = new_phase
    db.flush()


def validate_transfer_allowed(db: Session, transaction_id: str) -> CommodityTransaction:
    transaction = (
        db.query(CommodityTransaction)
        .options(joinedload(CommodityTransaction.legs).joinedload(TransactionLeg.asset_batch))
        .filter(CommodityTransaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise ValueError("Transaction not found")

    purchase = _get_leg(transaction, LegNumber.PURCHASE)
    if not purchase or purchase.status != LegStatus.CONFIRMED:
        raise ShariahStateViolation("Purchase leg must be confirmed before ownership transfer")

    assert_possession_sealed(db, transaction)
    return transaction
