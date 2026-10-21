from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session, joinedload

from tawarruq.api.deps import (
    require_manage_credentials,
    require_manage_institutions,
    require_tenant_access,
    require_write_ops,
    tenant_filter_institution_id,
)
from tawarruq.database import get_db
from tawarruq.enums import AuditActor, LegNumber, TransactionMode
from tawarruq.models.audit import AuditEvent
from tawarruq.models.application import FinancingApplication
from tawarruq.models.customer import Customer
from tawarruq.models.institution import Institution
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.schemas import (
    ApplicationCreate,
    ApplicationRead,
    AuditEventRead,
    DisbursementCreate,
    DisbursementRead,
    ErrorResponse,
    InstitutionCreate,
    InstitutionRead,
    MalaysiaFlowStatusRead,
    ManualBridgeConfirm,
    OfferCreate,
    OfferRead,
    TransactionCreate,
    TransactionRead,
)
from tawarruq.services import application_service, institution_service, malaysia_flow_service, transaction_service
from tawarruq.services.audit_query_service import query_audit_events
from tawarruq.services.audit_service import log_audit

router = APIRouter()

COMMON_ERRORS: dict = {
    400: {"model": ErrorResponse, "description": "Invalid request or business rule violation"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
}


@router.get(
    "/institutions",
    response_model=list[InstitutionRead],
    tags=["Institutions"],
    summary="List institutions",
    description="Returns all registered banks/Saccos. Each institution has a default BSAS backend mode.",
)
def list_institutions(db: Session = Depends(get_db)) -> list[InstitutionRead]:
    return db.query(Institution).order_by(Institution.name).all()


@router.post(
    "/institutions",
    response_model=InstitutionRead,
    status_code=201,
    tags=["Institutions"],
    summary="Register institution",
    description=(
        "Register a new institution. Set `bsas_mode` to control the default backend: "
        "`mock` for testing, `manual_bridge` while awaiting BSAS API access, `live` when connected."
    ),
    responses={400: {"model": ErrorResponse, "description": "Duplicate institution code"}},
)
def create_institution(
    payload: InstitutionCreate, request: Request, db: Session = Depends(get_db)
) -> InstitutionRead:
    require_manage_institutions(request)
    existing = db.query(Institution).filter(Institution.code == payload.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Institution code {payload.code} already exists")

    valid_modes = {TransactionMode.MOCK, TransactionMode.MANUAL_BRIDGE, TransactionMode.LIVE}
    if payload.bsas_mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"bsas_mode must be one of: {', '.join(valid_modes)}")

    institution = Institution(name=payload.name, code=payload.code, bsas_mode=payload.bsas_mode)
    db.add(institution)
    db.flush()
    log_audit(
        db,
        entity_type="institution",
        entity_id=institution.id,
        actor=AuditActor.HUMAN,
        action="institution.created",
        details=f"code={payload.code}, mode={payload.bsas_mode}",
    )
    db.commit()
    db.refresh(institution)
    return institution


@router.delete(
    "/institutions/{institution_id}",
    status_code=204,
    tags=["Institutions"],
    summary="Delete an institution and its tenant records",
)
def delete_institution(institution_id: str, request: Request, db: Session = Depends(get_db)) -> None:
    require_manage_institutions(request)
    institution = db.get(Institution, institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    try:
        institution_service.delete_institution(db, institution)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/applications",
    response_model=list[ApplicationRead],
    tags=["Applications"],
    summary="List applications",
    description="Browse financing applications with optional filters.",
)
def list_applications(
    request: Request,
    status: str | None = None,
    institution_id: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    scoped_institution = tenant_filter_institution_id(request, institution_id)
    query = (
        db.query(FinancingApplication)
        .options(joinedload(FinancingApplication.customer), joinedload(FinancingApplication.institution))
        .order_by(FinancingApplication.created_at.desc())
    )
    if status:
        query = query.filter(FinancingApplication.status == status)
    if scoped_institution:
        query = query.filter(FinancingApplication.institution_id == scoped_institution)
    return [application_service.to_application_read(item) for item in query.offset(offset).limit(limit).all()]


@router.post(
    "/applications",
    response_model=ApplicationRead,
    status_code=201,
    tags=["Applications"],
    summary="Create financing application",
    description=(
        "**Step 1** of the Tawarruq flow. Customer applies for financing.\n\n"
        "Pass `customer_id` to attach the deal to an onboarded customer. "
        "Omit `customer_ref` to auto-generate (format: `CUST-{INST_CODE}-{YYYY}-{NNNN}`). "
        "Omit `institution_id` to use the default institution (code: `DEFAULT`). "
        "Application starts in `draft` status until an offer is generated."
    ),
    responses=COMMON_ERRORS,
)
def create_application(
    payload: ApplicationCreate, request: Request, db: Session = Depends(get_db)
) -> ApplicationRead:
    require_write_ops(request)
    tenant_id = tenant_filter_institution_id(request, payload.institution_id)
    if tenant_id and payload.institution_id and payload.institution_id != tenant_id:
        raise HTTPException(status_code=403, detail="Cannot create application for another institution")
    if payload.customer_id:
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        require_tenant_access(request, customer.institution_id)
        if tenant_id and customer.institution_id != tenant_id:
            raise HTTPException(status_code=403, detail="Customer belongs to another institution")
        tenant_id = customer.institution_id
    try:
        application = application_service.create_application(
            db,
            customer_ref=payload.customer_ref,
            customer_name=payload.customer_name,
            customer_id=payload.customer_id,
            currency=payload.currency,
            amount_requested=payload.amount_requested,
            term_months=payload.term_months,
            purpose=payload.purpose,
            institution_id=tenant_id or payload.institution_id,
            institution_code=payload.institution_code if not tenant_id else None,
        )
        db.commit()
        db.refresh(application)
        return application_service.to_application_read(application)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationRead,
    tags=["Applications"],
    summary="Get application",
    description="Retrieve a single financing application by UUID.",
    responses={404: COMMON_ERRORS[404]},
)
def get_application(application_id: str, request: Request, db: Session = Depends(get_db)) -> ApplicationRead:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    if application.customer_id:
        _ = application.customer
    _ = application.institution
    return application_service.to_application_read(application)


@router.delete(
    "/applications/{application_id}",
    status_code=204,
    tags=["Applications"],
    summary="Delete a financing application and its journey records",
)
def delete_application(application_id: str, request: Request, db: Session = Depends(get_db)) -> None:
    require_write_ops(request)
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    try:
        application_service.delete_application(db, application)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/applications/{application_id}/offer",
    response_model=OfferRead,
    status_code=201,
    tags=["Applications"],
    summary="Generate financing offer",
    description=(
        "**Step 2a.** Institution presents cost price, profit, and total payable.\n\n"
        "- `cost_price` defaults to `amount_requested` if omitted.\n"
        "- `profit_amount` = cost_price × (profit_rate_pct / 100).\n"
        "- Moves application to `offer_pending`."
    ),
    responses=COMMON_ERRORS,
)
def generate_offer(
    application_id: str, payload: OfferCreate, request: Request, db: Session = Depends(get_db)
) -> OfferRead:
    require_write_ops(request)
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    try:
        offer = application_service.create_offer(
            db,
            application_id,
            cost_price=payload.cost_price,
            profit_rate_pct=payload.profit_rate_pct,
        )
        db.commit()
        db.refresh(offer)
        return offer
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/applications/{application_id}/accept",
    response_model=OfferRead,
    tags=["Applications"],
    summary="Accept financing offer",
    description=(
        "**Step 2b.** Record customer acceptance of the offer.\n\n"
        "Moves application to `offer_accepted`. Amanah may auto-create a commodity transaction "
        "if the worker is enabled with write access."
    ),
    responses=COMMON_ERRORS,
)
def accept_offer(application_id: str, request: Request, db: Session = Depends(get_db)) -> OfferRead:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    from tawarruq.api.approval_http import queued_or_none

    queued = queued_or_none(
        db,
        request,
        action="application.accept_offer",
        institution_id=application.institution_id,
        amount=application.amount_requested,
        application_id=application.id,
        currency=application.currency or "KES",
    )
    if queued:
        return queued  # type: ignore[return-value]
    try:
        offer = application_service.accept_offer(db, application_id)
        db.commit()
        db.refresh(offer)
        return offer
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/transactions",
    response_model=list[TransactionRead],
    tags=["Transactions"],
    summary="List transactions",
    description="Browse commodity transactions with optional filters.",
)
def list_transactions(
    request: Request,
    status: str | None = None,
    mode: str | None = None,
    institution_id: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[TransactionRead]:
    scoped_institution = tenant_filter_institution_id(request, institution_id)
    query = db.query(CommodityTransaction).order_by(CommodityTransaction.created_at.desc())
    if status:
        query = query.filter(CommodityTransaction.status == status)
    if mode:
        query = query.filter(CommodityTransaction.mode == mode)
    if scoped_institution:
        query = query.filter(CommodityTransaction.institution_id == scoped_institution)
    ids = [row.id for row in query.offset(offset).limit(limit).all()]
    return [
        detail
        for txn_id in ids
        if (detail := transaction_service.get_transaction_detail(db, txn_id))
    ]


@router.post(
    "/transactions",
    response_model=TransactionRead,
    status_code=201,
    tags=["Transactions"],
    summary="Start commodity transaction",
    description=(
        "**Step 3.** Creates a `CommodityTransaction` with 3 pending legs.\n\n"
        "Requires application in `offer_accepted` status.\n\n"
        "**For Swagger testing, set `mode` to `\"mock\"`** for instant leg confirmation."
    ),
    responses=COMMON_ERRORS,
)
def create_transaction(
    payload: TransactionCreate, request: Request, db: Session = Depends(get_db)
) -> TransactionRead:
    require_write_ops(request)
    application = db.get(FinancingApplication, payload.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    try:
        transaction = transaction_service.create_transaction(
            db,
            application_id=payload.application_id,
            commodity_code=payload.commodity_code,
            mode=payload.mode,
        )
        db.commit()
        detail = transaction_service.get_transaction_detail(db, transaction.id)
        return detail  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/transactions/{transaction_id}",
    response_model=TransactionRead,
    tags=["Transactions"],
    summary="Get full transaction status",
    description=(
        "Returns the complete multi-leg status in one call: all legs, certificates, timestamps, and mode.\n\n"
        "This is the primary ops endpoint for tracing a Tawarruq execution."
    ),
    responses={404: COMMON_ERRORS[404]},
)
def get_transaction(transaction_id: str, request: Request, db: Session = Depends(get_db)) -> TransactionRead:
    transaction = transaction_service.get_transaction_detail(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    require_tenant_access(request, transaction.institution_id)
    return transaction


@router.post(
    "/transactions/{transaction_id}/legs/purchase",
    response_model=TransactionRead,
    tags=["Transactions"],
    summary="Execute Leg 1: Agent purchase (BSAS)",
    description=(
        "**Leg 1.** Engine buys commodity as agent via BSAS. Returns e-certificate on confirmation.\n\n"
        "Executes the next pending leg in sequence. Prior legs must be confirmed."
    ),
    responses=COMMON_ERRORS,
)
def execute_purchase_leg(transaction_id: str, request: Request, db: Session = Depends(get_db)) -> TransactionRead:
    return _execute_leg(transaction_id, request, db)


@router.post(
    "/transactions/{transaction_id}/legs/transfer",
    response_model=TransactionRead,
    tags=["Transactions"],
    summary="Execute Leg 2: Ownership transfer (OTC)",
    description=(
        "**Leg 2.** Ownership of the commodity transfers to the customer (over-the-counter).\n\n"
        "Leg 1 must be `confirmed` before this executes."
    ),
    responses=COMMON_ERRORS,
)
def execute_transfer_leg(transaction_id: str, request: Request, db: Session = Depends(get_db)) -> TransactionRead:
    return _execute_leg(transaction_id, request, db)


@router.post(
    "/transactions/{transaction_id}/legs/sale",
    response_model=TransactionRead,
    tags=["Transactions"],
    summary="Execute Leg 3: Sale to BMIS (STB)",
    description=(
        "**Leg 3.** Engine sells commodity to BMIS on customer's behalf (STB).\n\n"
        "Legs 1 and 2 must be `confirmed`. After this leg, transaction status becomes `completed`."
    ),
    responses=COMMON_ERRORS,
)
def execute_sale_leg(transaction_id: str, request: Request, db: Session = Depends(get_db)) -> TransactionRead:
    return _execute_leg(transaction_id, request, db)


def _execute_leg(transaction_id: str, request: Request, db: Session) -> TransactionRead:
    from tawarruq.amanah.worker import AmanahWorker
    from tawarruq.models.transaction import CommodityTransaction

    transaction = db.get(CommodityTransaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    require_tenant_access(request, transaction.institution_id)
    require_write_ops(request)
    next_leg = next((leg for leg in transaction.legs if leg.status in {"pending", "in_progress"}), None)
    if next_leg and str(next_leg.leg_number) == "3":
        from tawarruq.api.approval_http import queued_or_none

        queued = queued_or_none(
            db,
            request,
            action="malaysia.sale_leg",
            institution_id=transaction.institution_id,
            application_id=transaction.application_id,
            transaction_id=transaction.id,
            payload={"transaction_id": transaction.id},
        )
        if queued:
            return queued  # type: ignore[return-value]

    worker = AmanahWorker(write_enabled=True)
    worker.process_transaction(db, transaction)
    db.commit()

    detail = transaction_service.get_transaction_detail(db, transaction_id)
    return detail  # type: ignore[return-value]


@router.post(
    "/transactions/{transaction_id}/legs/{leg_number}/confirm",
    response_model=TransactionRead,
    tags=["Transactions"],
    summary="Confirm manual-bridge leg certificate",
    description=(
        "For `manual_bridge` mode: ops submits the BSAS certificate number after manual processing.\n\n"
        "`leg_number`: `1` (purchase), `2` (transfer), or `3` (sale)."
    ),
    responses=COMMON_ERRORS,
)
def confirm_manual_leg(
    transaction_id: str,
    leg_number: str,
    payload: ManualBridgeConfirm,
    request: Request,
    db: Session = Depends(get_db),
) -> TransactionRead:
    if leg_number not in ("1", "2", "3"):
        raise HTTPException(status_code=400, detail="leg_number must be 1, 2, or 3")
    transaction = db.get(CommodityTransaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    require_tenant_access(request, transaction.institution_id)
    try:
        fields = payload.model_dump(exclude={"certificate_number", "issuer"}, exclude_none=True)
        transaction_service.confirm_manual_leg(
            db,
            transaction_id,
            LegNumber(leg_number),
            certificate_number=payload.certificate_number,
            issuer=payload.issuer,
            certificate_fields=fields,
            actor=AuditActor.HUMAN,
        )
        db.commit()
        detail = transaction_service.get_transaction_detail(db, transaction_id)
        return detail  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/disbursements",
    response_model=DisbursementRead,
    status_code=201,
    tags=["Disbursements"],
    summary="Trigger disbursement",
    description=(
        "**Step 12.** Disburse funds to customer and link Tawarruq certificate.\n\n"
        "Requires transaction status `completed` (all 3 legs confirmed)."
    ),
    responses=COMMON_ERRORS,
)
def create_disbursement(
    payload: DisbursementCreate, request: Request, db: Session = Depends(get_db)
) -> DisbursementRead:
    application = db.get(FinancingApplication, payload.application_id)
    if application:
        require_tenant_access(request, application.institution_id)
        from tawarruq.api.approval_http import queued_or_none

        queued = queued_or_none(
            db,
            request,
            action="malaysia.disburse",
            institution_id=application.institution_id,
            amount=application.amount_requested,
            application_id=application.id,
            transaction_id=payload.transaction_id,
            payload={"application_id": payload.application_id, "transaction_id": payload.transaction_id},
            currency=application.currency or "KES",
        )
        if queued:
            return queued  # type: ignore[return-value]
    try:
        disbursement = transaction_service.create_disbursement(
            db,
            application_id=payload.application_id,
            transaction_id=payload.transaction_id,
        )
        db.commit()
        from tawarruq.models.disbursement import Disbursement

        loaded = (
            db.query(Disbursement)
            .options(joinedload(Disbursement.tawarruq_certificate))
            .filter(Disbursement.id == disbursement.id)
            .first()
        )
        return loaded  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/malaysia/applications/{application_id}/run-full-flow",
    response_model=MalaysiaFlowStatusRead,
    tags=["Malaysia Manual Bridge"],
    summary="Demo: run complete mock Malaysia 3-leg flow",
    description=(
        "Mock-only one-click runner: Leg 1 purchase, Leg 2 transfer, customer sale and Wakala, "
        "Leg 3 sale, disbursement, and Tawarruq certificate. "
        "Suq Al-Sila' production uses `manual_bridge`. Eiger/live desks use LIVE credentials."
    ),
)
def run_full_malaysia_flow(application_id: str, request: Request, db: Session = Depends(get_db)) -> MalaysiaFlowStatusRead:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    require_write_ops(request)
    from tawarruq.api.approval_http import queued_or_none

    queued = queued_or_none(
        db,
        request,
        action="malaysia.run_full_flow",
        institution_id=application.institution_id,
        amount=application.amount_requested,
        application_id=application.id,
        currency=application.currency or "KES",
    )
    if queued:
        return queued  # type: ignore[return-value]
    try:
        result = malaysia_flow_service.run_ordered_malaysia_flow(db, application_id)
        db.commit()
        return MalaysiaFlowStatusRead(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/audit",
    response_model=list[AuditEventRead],
    tags=["Audit"],
    summary="Get audit trail",
    description="Immutable audit log. Filter by entity_id, entity_type, actor, or institution_id.",
)
def get_audit_trail(
    request: Request,
    entity_id: str | None = Query(None, description="UUID of the entity to audit"),
    entity_type: str | None = None,
    actor: str | None = None,
    institution_id: str | None = None,
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    limit: int = Query(500, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[AuditEventRead]:
    if not entity_id and not institution_id and not entity_type and not actor:
        raise HTTPException(status_code=400, detail="Provide at least one filter (entity_id, institution_id, etc.)")
    scoped_institution = tenant_filter_institution_id(request, institution_id)
    return query_audit_events(
        db,
        entity_id=entity_id,
        entity_type=entity_type,
        actor=actor,
        institution_id=scoped_institution,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
    )
