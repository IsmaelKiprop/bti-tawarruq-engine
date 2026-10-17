import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from tawarruq.amanah.escalation import escalate
from tawarruq.amanah.kenya_orchestrator import auto_create_kenya_transaction, process_mno_transaction
from tawarruq.services.kenya_flow_service import get_mno_transaction
from tawarruq.bsas.context_builder import build_leg_context
from tawarruq.bsas.base import LegExecutionResult
from tawarruq.bsas.factory import get_bsas_backend
from tawarruq.config import get_settings
from tawarruq.database import SessionLocal
from tawarruq.enums import (
    ApplicationStatus,
    AuditActor,
    LegNumber,
    LegStatus,
    TransactionMode,
    TransactionStatus,
    WebhookEvent,
)
from tawarruq.models.application import FinancingApplication
from tawarruq.models.execution import TawarruqExecution
from tawarruq.models.transaction import CommodityTransaction, TransactionLeg
from tawarruq.services.audit_service import log_audit
from tawarruq.services.business_flow_service import (
    appoint_customer_agency,
    business_steps_ready_for_leg3,
    record_customer_sale,
)
from tawarruq.services.transaction_service import (
    refresh_transaction_status,
    update_leg_from_execution,
)
from tawarruq.services.webhook_service import dispatch_webhook_event

logger = logging.getLogger(__name__)

LEG_ORDER = [LegNumber.PURCHASE, LegNumber.TRANSFER, LegNumber.SALE]


class AmanahWorker:
    """Amanah orchestrates Tawarruq legs after offer acceptance."""

    def __init__(self, write_enabled: bool | None = None) -> None:
        settings = get_settings()
        self.write_enabled = settings.amanah_write_enabled if write_enabled is None else write_enabled
        self.poll_interval = settings.amanah_poll_interval_seconds
        self.cert_timeout = settings.amanah_certificate_timeout_seconds

    def _next_pending_leg(self, transaction: CommodityTransaction) -> TransactionLeg | None:
        for leg_num in LEG_ORDER:
            leg = next((item for item in transaction.legs if item.leg_number == leg_num), None)
            if leg and leg.status in (LegStatus.PENDING, LegStatus.AWAITING_CONFIRMATION, LegStatus.IN_PROGRESS):
                return leg
        return None

    def _build_context(self, db: Session, transaction: CommodityTransaction, leg: TransactionLeg):
        return build_leg_context(db, transaction, leg)

    def _check_amount_consistency(self, db: Session, transaction: CommodityTransaction) -> bool:
        application = db.get(FinancingApplication, transaction.application_id)
        if not application or not application.offer:
            escalate("Amount mismatch: application has no offer", entity_id=transaction.id)
            return False
        expected = Decimal(str(application.offer.cost_price))
        if expected <= 0:
            escalate("Amount mismatch: invalid cost price", entity_id=transaction.id)
            return False
        context_amount = Decimal(str(self._build_context(db, transaction, transaction.legs[0]).amount))
        if context_amount != expected:
            escalate(
                f"Amount mismatch: leg amount {context_amount} != offer {expected}",
                entity_id=transaction.id,
            )
            return False
        return True

    def _ensure_business_steps(self, db: Session, application: FinancingApplication) -> None:
        if not application.customer_sale:
            record_customer_sale(db, application.id, actor=AuditActor.AI_WORKER)
        if not application.customer_agency:
            appoint_customer_agency(db, application.id, notes="Auto-appointed by Amanah after Leg 2", actor=AuditActor.AI_WORKER)

    def _check_certificate_timeout(self, db: Session, transaction: CommodityTransaction, leg: TransactionLeg) -> bool:
        if leg.status != LegStatus.AWAITING_CONFIRMATION:
            return False
        deadline = leg.updated_at.replace(tzinfo=UTC) + timedelta(seconds=self.cert_timeout)
        if datetime.now(UTC) <= deadline:
            return False
        transaction.status = TransactionStatus.ESCALATED
        transaction.application.status = ApplicationStatus.ESCALATED
        escalate(
            f"Certificate timeout on Leg {leg.leg_number} (ref: {leg.external_ref})",
            entity_id=transaction.id,
            evidence_ref=leg.external_ref,
        )
        dispatch_webhook_event(
            db,
            institution_id=transaction.institution_id,
            event=WebhookEvent.TRANSACTION_ESCALATED,
            data={"transaction_id": transaction.id, "reason": "certificate_timeout", "leg": leg.leg_number},
        )
        log_audit(
            db,
            entity_type="commodity_transaction",
            entity_id=transaction.id,
            actor=AuditActor.AI_WORKER,
            action="transaction.escalated",
            details=f"certificate_timeout leg={leg.leg_number}",
        )
        return True

    def process_transaction(self, db: Session, transaction: CommodityTransaction) -> None:
        if transaction.status in (TransactionStatus.COMPLETED, TransactionStatus.FAILED, TransactionStatus.ESCALATED):
            return

        if transaction.mode in {TransactionMode.MNO, TransactionMode.AGENT_DEALER}:
            process_mno_transaction(db, transaction, write_enabled=self.write_enabled)
            db.commit()
            return

        application = (
            db.query(FinancingApplication)
            .options(
                joinedload(FinancingApplication.offer),
                joinedload(FinancingApplication.customer_sale),
                joinedload(FinancingApplication.customer_agency),
            )
            .filter(FinancingApplication.id == transaction.application_id)
            .first()
        )
        if not application:
            return

        if not self._check_amount_consistency(db, transaction):
            transaction.status = TransactionStatus.ESCALATED
            application.status = ApplicationStatus.ESCALATED
            dispatch_webhook_event(
                db,
                institution_id=transaction.institution_id,
                event=WebhookEvent.TRANSACTION_ESCALATED,
                data={"transaction_id": transaction.id, "reason": "amount_mismatch"},
            )
            log_audit(
                db,
                entity_type="commodity_transaction",
                entity_id=transaction.id,
                actor=AuditActor.AI_WORKER,
                action="transaction.escalated",
                details="amount_consistency_check_failed",
            )
            db.commit()
            return

        leg = self._next_pending_leg(transaction)
        if not leg:
            refresh_transaction_status(db, transaction)
            db.commit()
            return

        if self._check_certificate_timeout(db, transaction, leg):
            db.commit()
            return

        leg_idx = LEG_ORDER.index(LegNumber(leg.leg_number))
        if leg_idx > 0:
            prior = next(item for item in transaction.legs if item.leg_number == LEG_ORDER[leg_idx - 1])
            if prior.status != LegStatus.CONFIRMED:
                return
            if LegNumber(leg.leg_number) == LegNumber.SALE and prior.leg_number == LegNumber.TRANSFER:
                if self.write_enabled:
                    self._ensure_business_steps(db, application)
                if not business_steps_ready_for_leg3(db, application.id):
                    return

        backend = get_bsas_backend(transaction.mode)

        if leg.status == LegStatus.AWAITING_CONFIRMATION and leg.external_ref:
            if not self.write_enabled:
                return
            cert_response = backend.get_certificate(leg.external_ref)
            if cert_response and cert_response.result == LegExecutionResult.CONFIRMED:
                update_leg_from_execution(
                    db,
                    leg,
                    status=LegStatus.CONFIRMED,
                    external_ref=cert_response.external_ref,
                    certificate_number=cert_response.certificate_number,
                    issuer=cert_response.issuer,
                    bsas_fee=cert_response.bsas_fee,
                    actor=AuditActor.AI_WORKER,
                )
                if LegNumber(leg.leg_number) == LegNumber.TRANSFER and self.write_enabled:
                    db.refresh(application)
                    self._ensure_business_steps(db, application)
                refresh_transaction_status(db, transaction)
                log_audit(
                    db,
                    entity_type="transaction_leg",
                    entity_id=leg.id,
                    actor=AuditActor.AI_WORKER,
                    action="leg.certificate_parsed",
                    evidence_ref=cert_response.certificate_number,
                )
            db.commit()
            return

        if leg.status == LegStatus.PENDING:
            if not self.write_enabled:
                log_audit(
                    db,
                    entity_type="transaction_leg",
                    entity_id=leg.id,
                    actor=AuditActor.AI_WORKER,
                    action="leg.observed_pending",
                    details=f"read-only mode, leg {leg.leg_number}",
                )
                db.commit()
                return

            context = self._build_context(db, transaction, leg)
            leg.status = LegStatus.IN_PROGRESS
            db.flush()

            response = backend.execute_leg(context)

            if response.result == LegExecutionResult.FAILED:
                update_leg_from_execution(
                    db,
                    leg,
                    status=LegStatus.FAILED,
                    error_message=response.error_message,
                    actor=AuditActor.AI_WORKER,
                )
                transaction.status = TransactionStatus.FAILED
                dispatch_webhook_event(
                    db,
                    institution_id=transaction.institution_id,
                    event=WebhookEvent.TRANSACTION_FAILED,
                    data={"transaction_id": transaction.id, "leg": leg.leg_number},
                )
                escalate(f"Leg {leg.leg_number} failed: {response.error_message}", entity_id=transaction.id)
            elif response.result == LegExecutionResult.AWAITING_CONFIRMATION:
                leg.status = LegStatus.AWAITING_CONFIRMATION
                leg.external_ref = response.external_ref
                transaction.status = TransactionStatus.AWAITING_MANUAL
                log_audit(
                    db,
                    entity_type="transaction_leg",
                    entity_id=leg.id,
                    actor=AuditActor.AI_WORKER,
                    action="leg.manual_request_generated",
                    evidence_ref=response.manual_request_path,
                )
            else:
                update_leg_from_execution(
                    db,
                    leg,
                    status=LegStatus.CONFIRMED,
                    external_ref=response.external_ref,
                    certificate_number=response.certificate_number,
                    issuer=response.issuer,
                    bsas_fee=response.bsas_fee,
                    actor=AuditActor.AI_WORKER,
                )
                if LegNumber(leg.leg_number) == LegNumber.TRANSFER and self.write_enabled:
                    db.refresh(application)
                    self._ensure_business_steps(db, application)

            refresh_transaction_status(db, transaction)
            db.commit()

    def tick(self) -> None:
        db = SessionLocal()
        try:
            kenya_apps = (
                db.query(FinancingApplication)
                .filter(
                    FinancingApplication.customer_id.isnot(None),
                    FinancingApplication.eligibility_passed.is_(True),
                    FinancingApplication.status.in_(
                        [ApplicationStatus.DRAFT, ApplicationStatus.IN_PROGRESS, ApplicationStatus.OFFER_ACCEPTED]
                    ),
                )
                .all()
            )

            for application in kenya_apps:
                if db.query(TawarruqExecution).filter(TawarruqExecution.application_id == application.id).first():
                    continue
                if self.write_enabled and not get_mno_transaction(db, application.id):
                    auto_create_kenya_transaction(db, application)
                    db.commit()

            applications = (
                db.query(FinancingApplication)
                .filter(
                    FinancingApplication.status.in_(
                        [ApplicationStatus.OFFER_ACCEPTED, ApplicationStatus.IN_PROGRESS]
                    )
                )
                .all()
            )

            for application in applications:
                if db.query(TawarruqExecution).filter(TawarruqExecution.application_id == application.id).first():
                    continue
                if application.status == ApplicationStatus.OFFER_ACCEPTED and self.write_enabled:
                    if not (application.customer_id and application.eligibility_passed):
                        from tawarruq.services.transaction_service import create_transaction

                        create_transaction(db, application_id=application.id, actor=AuditActor.AI_WORKER)
                        log_audit(
                            db,
                            entity_type="financing_application",
                            entity_id=application.id,
                            actor=AuditActor.AI_WORKER,
                            action="transaction.auto_created",
                        )
                        db.commit()

            transactions = (
                db.query(CommodityTransaction)
                .options(
                    joinedload(CommodityTransaction.legs),
                    joinedload(CommodityTransaction.institution),
                )
                .filter(
                    CommodityTransaction.status.in_(
                        [
                            TransactionStatus.CREATED,
                            TransactionStatus.EXECUTING,
                            TransactionStatus.AWAITING_POSSESSION,
                        ]
                    )
                )
                .all()
            )

            for transaction in transactions:
                self.process_transaction(db, transaction)

        except Exception as exc:
            logger.exception("Amanah tick failed: %s", exc)
            db.rollback()
        finally:
            db.close()

    async def run_forever(self) -> None:
        mode = "write-enabled" if self.write_enabled else "read-only"
        logger.info("Amanah worker started (%s), poll interval=%ss", mode, self.poll_interval)
        while True:
            self.tick()
            await asyncio.sleep(self.poll_interval)
