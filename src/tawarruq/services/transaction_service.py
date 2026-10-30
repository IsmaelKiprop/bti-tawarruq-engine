from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

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
from tawarruq.models.certificate import Certificate
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.transaction import CommodityTransaction, TransactionLeg
from tawarruq.services.audit_service import log_audit
from tawarruq.services.business_flow_service import issue_tawarruq_certificate
from tawarruq.services.malaysia_shariah_service import log_malaysia_disbursement, log_malaysia_leg
from tawarruq.services.webhook_service import dispatch_webhook_event


def create_transaction(
    db: Session,
    *,
    application_id: str,
    commodity_code: str = "PALM_OIL",
    mode: str | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> CommodityTransaction:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise ValueError(f"Application {application_id} not found")
    if application.status != ApplicationStatus.OFFER_ACCEPTED:
        raise ValueError(f"Application must be in offer_accepted status, got {application.status}")

    institution = application.institution
    resolved_mode = mode or institution.bsas_mode

    transaction = CommodityTransaction(
        application_id=application.id,
        institution_id=institution.id,
        commodity_code=commodity_code,
        mode=resolved_mode,
        status=TransactionStatus.CREATED,
    )
    db.add(transaction)
    db.flush()

    for leg_num in (LegNumber.PURCHASE, LegNumber.TRANSFER, LegNumber.SALE):
        db.add(
            TransactionLeg(
                transaction_id=transaction.id,
                leg_number=leg_num,
                status=LegStatus.PENDING,
            )
        )
    db.flush()

    application.status = ApplicationStatus.IN_PROGRESS
    log_audit(
        db,
        entity_type="commodity_transaction",
        entity_id=transaction.id,
        actor=actor,
        action="transaction.created",
        details=f"mode={resolved_mode}, commodity={commodity_code}",
    )
    dispatch_webhook_event(
        db,
        institution_id=institution.id,
        event=WebhookEvent.TRANSACTION_CREATED,
        data={"transaction_id": transaction.id, "application_id": application.id, "mode": resolved_mode},
    )
    return transaction


def get_transaction_detail(db: Session, transaction_id: str) -> CommodityTransaction | None:
    return (
        db.query(CommodityTransaction)
        .options(
            joinedload(CommodityTransaction.legs).joinedload(TransactionLeg.certificate),
        )
        .filter(CommodityTransaction.id == transaction_id)
        .first()
    )


def _get_leg(transaction: CommodityTransaction, leg_number: LegNumber) -> TransactionLeg:
    for leg in transaction.legs:
        if leg.leg_number == leg_number:
            return leg
    raise ValueError(f"Leg {leg_number} not found on transaction {transaction.id}")


def _prior_leg_confirmed(transaction: CommodityTransaction, leg_number: LegNumber) -> bool:
    order = [LegNumber.PURCHASE, LegNumber.TRANSFER, LegNumber.SALE]
    idx = order.index(leg_number)
    if idx == 0:
        return True
    prior = _get_leg(transaction, order[idx - 1])
    return prior.status == LegStatus.CONFIRMED


def update_leg_from_execution(
    db: Session,
    leg: TransactionLeg,
    *,
    status: LegStatus,
    external_ref: str | None = None,
    error_message: str | None = None,
    certificate_number: str | None = None,
    issuer: str = "Bursa Malaysia Islamic Services Sdn.Bhd.",
    bsas_fee: float | None = None,
    certificate_fields: dict | None = None,
    actor: AuditActor = AuditActor.AI_WORKER,
) -> TransactionLeg:
    leg.status = status
    if external_ref:
        leg.external_ref = external_ref
    if error_message:
        leg.error_message = error_message
    if bsas_fee is not None:
        leg.bsas_fee = bsas_fee
    if status == LegStatus.CONFIRMED:
        leg.executed_at = datetime.now(UTC)
    if certificate_number and status == LegStatus.CONFIRMED:
        fields = certificate_fields or {}
        cert = Certificate(
            leg_id=leg.id,
            certificate_number=certificate_number,
            issuer=issuer,
            seller=fields.get("seller"),
            buyer=fields.get("buyer"),
            bid_no=fields.get("bid_no"),
            selling_time=fields.get("selling_time"),
            selling_date=fields.get("selling_date"),
            value_date=fields.get("value_date"),
            product_code=fields.get("product_code"),
            product_description=fields.get("product_description"),
            unit=fields.get("unit"),
            volume=fields.get("volume"),
            currency=fields.get("currency"),
            price=fields.get("price"),
            price_myr_equivalent=fields.get("price_myr_equivalent"),
            value_amount=fields.get("value_amount"),
            transaction_type=fields.get("transaction_type"),
            pdf_path=fields.get("pdf_path"),
            pdf_filename=fields.get("pdf_filename"),
            details_json=fields.get("details_json"),
        )
        db.add(cert)
        db.flush()
        log_audit(
            db,
            entity_type="certificate",
            entity_id=cert.id,
            actor=actor,
            action="certificate.received",
            evidence_ref=certificate_number,
            details=fields.get("pdf_filename"),
        )
    log_audit(
        db,
        entity_type="transaction_leg",
        entity_id=leg.id,
        actor=actor,
        action=f"leg.{leg.leg_number}.{status}",
        details=error_message or external_ref,
        evidence_ref=certificate_number,
    )
    if status == LegStatus.CONFIRMED:
        txn = db.get(CommodityTransaction, leg.transaction_id)
        if txn:
            application = (
                db.query(FinancingApplication)
                .options(joinedload(FinancingApplication.institution))
                .filter(FinancingApplication.id == txn.application_id)
                .first()
            )
            if application and txn.mode != TransactionMode.MNO:
                log_malaysia_leg(
                    db,
                    transaction_id=txn.id,
                    leg_number=leg.leg_number,
                    application=application,
                    certificate_number=certificate_number,
                )
            dispatch_webhook_event(
                db,
                institution_id=txn.institution_id,
                event=WebhookEvent.LEG_CONFIRMED,
                data={"transaction_id": txn.id, "leg_number": leg.leg_number, "certificate": certificate_number},
            )
    db.flush()
    return leg


def refresh_transaction_status(db: Session, transaction: CommodityTransaction) -> None:
    legs = sorted(transaction.legs, key=lambda leg: leg.leg_number)
    if any(leg.status == LegStatus.FAILED for leg in legs):
        transaction.status = TransactionStatus.FAILED
        return
    if any(leg.status == LegStatus.AWAITING_POSSESSION for leg in legs):
        transaction.status = TransactionStatus.AWAITING_POSSESSION
        return
    if any(leg.status == LegStatus.AWAITING_CONFIRMATION for leg in legs):
        transaction.status = TransactionStatus.AWAITING_MANUAL
        return
    if all(leg.status == LegStatus.CONFIRMED for leg in legs):
        transaction.status = TransactionStatus.COMPLETED
        transaction.application.status = ApplicationStatus.COMPLETED
        dispatch_webhook_event(
            db,
            institution_id=transaction.institution_id,
            event=WebhookEvent.TRANSACTION_COMPLETED,
            data={"transaction_id": transaction.id, "application_id": transaction.application_id},
        )
        return
    if any(leg.status in (LegStatus.IN_PROGRESS, LegStatus.CONFIRMED) for leg in legs):
        transaction.status = TransactionStatus.EXECUTING


def create_disbursement(
    db: Session,
    *,
    application_id: str,
    transaction_id: str,
    actor: AuditActor = AuditActor.HUMAN,
) -> Disbursement:
    application = db.get(FinancingApplication, application_id)
    transaction = get_transaction_detail(db, transaction_id)
    if not application or not transaction:
        raise ValueError("Application or transaction not found")
    if transaction.status != TransactionStatus.COMPLETED:
        raise ValueError("Transaction must be completed before disbursement")
    if not application.offer:
        raise ValueError("Application has no offer")

    sale_leg = _get_leg(transaction, LegNumber.SALE)
    certificate_id = sale_leg.certificate.id if sale_leg.certificate else None

    disbursement = Disbursement(
        application_id=application.id,
        transaction_id=transaction.id,
        amount=Decimal(str(application.offer.cost_price)),
        certificate_id=certificate_id,
    )
    db.add(disbursement)
    db.flush()
    issue_tawarruq_certificate(db, disbursement, actor=actor)
    db.refresh(application, attribute_names=["institution"])
    log_malaysia_disbursement(
        db,
        application=application,
        disbursement_id=disbursement.id,
        amount=str(disbursement.amount),
    )
    log_audit(
        db,
        entity_type="disbursement",
        entity_id=disbursement.id,
        actor=actor,
        action="disbursement.created",
        details=f"amount={disbursement.amount}",
    )
    dispatch_webhook_event(
        db,
        institution_id=application.institution_id,
        event=WebhookEvent.DISBURSEMENT_CREATED,
        data={"disbursement_id": disbursement.id, "amount": str(disbursement.amount)},
    )
    try:
        from tawarruq.services.customer_notify_service import notify_step_ready

        notify_step_ready(
            db,
            email=getattr(application.customer, "email", None),
            customer_name=application.customer_name,
            customer_ref=application.customer_ref,
            title="Bursa disbursement",
            body_line="Funds have been disbursed. Open your journey for the Tawarruq certificate.",
            institution_name=application.institution.name if application.institution else None,
        )
    except Exception:
        pass
    return disbursement


def confirm_manual_leg(
    db: Session,
    transaction_id: str,
    leg_number: LegNumber,
    *,
    certificate_number: str,
    issuer: str = "Bursa Malaysia Islamic Services Sdn.Bhd.",
    certificate_fields: dict | None = None,
    actor: AuditActor = AuditActor.HUMAN,
) -> TransactionLeg:
    from tawarruq.services.manual_bridge_service import write_manual_reply

    transaction = get_transaction_detail(db, transaction_id)
    if not transaction:
        raise ValueError(f"Transaction {transaction_id} not found")
    if transaction.mode != TransactionMode.MANUAL_BRIDGE:
        raise ValueError("Certificate paste confirm is only for manual_bridge transactions")
    leg = _get_leg(transaction, leg_number)
    if leg.status not in (LegStatus.AWAITING_CONFIRMATION, LegStatus.IN_PROGRESS):
        raise ValueError(f"Leg {leg_number} is not awaiting confirmation")

    fields = dict(certificate_fields or {})
    if leg.external_ref:
        write_manual_reply(
            leg.external_ref,
            certificate_number=certificate_number,
            issuer=issuer,
            metadata=fields,
        )

    import json

    if fields and "details_json" not in fields:
        fields["details_json"] = json.dumps(
            {
                "certificate_number": certificate_number,
                "issuer": issuer,
                **{k: v for k, v in fields.items() if k not in ("pdf_path", "details_json") and v is not None},
            },
            indent=2,
        )

    update_leg_from_execution(
        db,
        leg,
        status=LegStatus.CONFIRMED,
        certificate_number=certificate_number,
        issuer=issuer,
        certificate_fields=fields,
        actor=actor,
    )
    refresh_transaction_status(db, transaction)
    if leg_number == LegNumber.TRANSFER:
        from tawarruq.services.business_flow_service import appoint_customer_agency, record_customer_sale

        application = db.get(FinancingApplication, transaction.application_id)
        if application and not application.customer_sale:
            record_customer_sale(db, application.id, actor=actor)
        if application and not application.customer_agency:
            appoint_customer_agency(
                db,
                application.id,
                notes="Recorded after Leg 2 confirm so Suq Al-Sila' Leg 3 can proceed",
                actor=actor,
            )
    log_audit(
        db,
        entity_type="commodity_transaction",
        entity_id=transaction.id,
        actor=actor,
        action="manual_bridge.confirmed",
        evidence_ref=certificate_number,
        details=f"leg={leg_number}",
    )
    try:
        from tawarruq.services.customer_notify_service import notify_step_ready

        application = db.get(FinancingApplication, transaction.application_id)
        if application:
            notify_step_ready(
                db,
                email=getattr(application.customer, "email", None),
                customer_name=application.customer_name,
                customer_ref=application.customer_ref,
                title=f"Bursa certificate leg {int(leg_number)}",
                body_line=f"E-certificate {certificate_number} has been recorded for this facility.",
                institution_name=application.institution.name if application.institution else None,
            )
    except Exception:
        pass
    return leg
