"""Bank Commodity Murabahah financing through Sedania AS SIDQ."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from tawarruq.api.deps import require_tenant_access, require_write_ops, resolve_write_institution_id, tenant_filter_institution_id
from tawarruq.database import get_db
from tawarruq.enums import ExecutionPath
from tawarruq.models.execution import TawarruqExecution
from tawarruq.models.institution import Institution
from tawarruq.schemas.sedania import (
    SedaniaDocumentIndex,
    SedaniaFinancingRead,
    SedaniaFinancingRequest,
    SedaniaPhysicalDeliveryRequest,
)
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.sedania_financing_service import (
    arrange_physical_delivery,
    execute_bank_financing,
    list_document_index,
    mark_repayment_settled,
    render_execution_document,
    to_financing_read,
)

router = APIRouter()


def _resolve_institution(db: Session, request: Request, payload: SedaniaFinancingRequest) -> Institution:
    requested = payload.institution_id
    if payload.institution_code and not requested:
        inst = db.query(Institution).filter(Institution.code == payload.institution_code).first()
        if not inst:
            raise HTTPException(status_code=404, detail=f"Institution {payload.institution_code} not found")
        requested = inst.id
    institution_id = resolve_write_institution_id(request, requested)
    if institution_id:
        inst = db.get(Institution, institution_id)
        if not inst:
            raise HTTPException(status_code=404, detail="Institution not found")
        return inst
    return db.query(Institution).filter(Institution.code == "DIB").first() or get_or_create_default_institution(db)


def _load_execution(db: Session, request: Request, execution_id: str) -> TawarruqExecution:
    execution = db.get(TawarruqExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    require_tenant_access(request, execution.institution_id)
    return execution


@router.post(
    "/sedania/financing",
    response_model=SedaniaFinancingRead,
    status_code=200,
    tags=["Sedania Financing"],
    summary="Run the Sedania bank financing flow",
    description=(
        "BTI Advisory approved flow (SASC as independent wakeel, muqassah, bank credits CASA) "
        "or the proposed AAOIFI Rasul flow. Physical delivery skips the independent sale."
    ),
)
def create_sedania_financing(
    payload: SedaniaFinancingRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SedaniaFinancingRead:
    require_write_ops(request)
    institution = _resolve_institution(db, request, payload)
    require_tenant_access(request, institution.id)
    execution = execute_bank_financing(db, payload, institution=institution)
    db.commit()
    db.refresh(execution)
    return to_financing_read(db, execution)


@router.get(
    "/sedania/financing",
    response_model=list[SedaniaFinancingRead],
    tags=["Sedania Financing"],
    summary="List Sedania financing runs",
)
def list_sedania_financing(
    request: Request,
    db: Session = Depends(get_db),
    institution_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[SedaniaFinancingRead]:
    scoped = tenant_filter_institution_id(request, institution_id)
    query = db.query(TawarruqExecution).order_by(TawarruqExecution.created_at.desc())
    if scoped:
        query = query.filter(TawarruqExecution.institution_id == scoped)
    query = query.filter(TawarruqExecution.path == ExecutionPath.BANK_FINANCING)
    return [to_financing_read(db, item) for item in query.limit(limit).all()]


@router.get(
    "/sedania/financing/{execution_id}",
    response_model=SedaniaFinancingRead,
    tags=["Sedania Financing"],
    summary="Read a Sedania financing run",
)
def get_sedania_financing(
    execution_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> SedaniaFinancingRead:
    return to_financing_read(db, _load_execution(db, request, execution_id))


@router.get(
    "/sedania/financing/{execution_id}/documents",
    response_model=list[SedaniaDocumentIndex],
    tags=["Sedania Financing"],
    summary="List the AS SIDQ trade pack",
)
def list_sedania_documents(
    execution_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> list[SedaniaDocumentIndex]:
    return list_document_index(db, _load_execution(db, request, execution_id))


@router.get(
    "/sedania/financing/{execution_id}/documents/{kind}",
    tags=["Sedania Financing"],
    summary="Download a Sedania trade document",
)
def download_sedania_document(
    execution_id: str,
    kind: str,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    execution = _load_execution(db, request, execution_id)
    try:
        html, filename = render_execution_document(db, execution, kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post(
    "/sedania/financing/{execution_id}/settle",
    response_model=SedaniaFinancingRead,
    tags=["Sedania Financing"],
    summary="Mark the deferred Murabahah price fully settled",
)
def settle_sedania_financing(
    execution_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> SedaniaFinancingRead:
    require_write_ops(request)
    execution = _load_execution(db, request, execution_id)
    mark_repayment_settled(db, execution)
    db.commit()
    db.refresh(execution)
    return to_financing_read(db, execution)


@router.post(
    "/sedania/financing/{execution_id}/physical-delivery",
    response_model=SedaniaFinancingRead,
    tags=["Sedania Financing"],
    summary="Arrange physical delivery (qabd hakiki)",
)
def physical_delivery_sedania_financing(
    execution_id: str,
    request: Request,
    payload: SedaniaPhysicalDeliveryRequest | None = None,
    db: Session = Depends(get_db),
) -> SedaniaFinancingRead:
    require_write_ops(request)
    execution = _load_execution(db, request, execution_id)
    body = payload or SedaniaPhysicalDeliveryRequest()
    if body.mark_settled:
        mark_repayment_settled(db, execution)
    arrange_physical_delivery(db, execution)
    db.commit()
    db.refresh(execution)
    return to_financing_read(db, execution)
