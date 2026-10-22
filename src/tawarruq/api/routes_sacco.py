"""SACCO CBS inbound execute API and certificate vault reads."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from tawarruq.api.deps import require_tenant_access, require_write_ops, resolve_write_institution_id
from tawarruq.database import get_db
from tawarruq.models.execution import TawarruqExecution
from tawarruq.models.institution import Institution
from tawarruq.schemas.sacco import SaccoExecuteRequest
from tawarruq.schemas.sedania import SedaniaFinancingRead
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.auth_service import require_sacco_hmac
from tawarruq.services.certificate_vault_service import get_vault_certificate
from tawarruq.services.sacco_execute_service import execute_sacco_facility, to_execute_read

router = APIRouter()


def _resolve_institution(db: Session, request: Request, payload: SaccoExecuteRequest) -> Institution:
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
    return db.query(Institution).filter(Institution.code == "MWALIMU").first() or get_or_create_default_institution(db)


@router.post(
    "/tawarruq/execute",
    response_model=SedaniaFinancingRead,
    status_code=200,
    tags=["SACCO Execute"],
    summary="Inbound SACCO facility request",
    description=(
        "Mwalimu (or any SACCO CBS) starts Tawarruq here. Buruuj stamps Wa'd and Wakalah, "
        "calls Sedania for purchase / Murabahah / independent liquidation, vaults the three "
        "certificates for 7 years, then webhooks the SACCO. Buruuj never disburses principal cash."
    ),
)
async def execute_tawarruq(request: Request, db: Session = Depends(get_db)) -> SedaniaFinancingRead:
    require_write_ops(request)
    raw = await request.body()
    require_sacco_hmac(request, db, raw)
    try:
        payload = SaccoExecuteRequest.model_validate_json(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    institution = _resolve_institution(db, request, payload)
    require_tenant_access(request, institution.id)
    execution = execute_sacco_facility(db, payload, institution=institution)
    db.commit()
    db.refresh(execution)
    return to_execute_read(db, execution)


@router.get(
    "/tawarruq/executions/{execution_id}",
    response_model=SedaniaFinancingRead,
    tags=["SACCO Execute"],
    summary="Read a SACCO execute run",
)
def get_execution(execution_id: str, request: Request, db: Session = Depends(get_db)) -> SedaniaFinancingRead:
    execution = db.get(TawarruqExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    require_tenant_access(request, execution.institution_id)
    return to_execute_read(db, execution)


@router.get(
    "/tawarruq/executions",
    response_model=list[SedaniaFinancingRead],
    tags=["SACCO Execute"],
    summary="List SACCO execute runs",
)
def list_executions(
    request: Request,
    db: Session = Depends(get_db),
    institution_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[SedaniaFinancingRead]:
    from tawarruq.api.deps import tenant_filter_institution_id

    scoped = tenant_filter_institution_id(request, institution_id)
    query = db.query(TawarruqExecution).order_by(TawarruqExecution.created_at.desc())
    if scoped:
        query = query.filter(TawarruqExecution.institution_id == scoped)
    return [to_execute_read(db, item) for item in query.limit(limit).all()]


@router.get(
    "/tawarruq/certificates/{vault_id}",
    tags=["SACCO Execute"],
    summary="Fetch a vaulted certificate payload",
    description="Tokenised URL from the SACCO webhook. Payloads are retained for 7 years.",
)
def get_vaulted_certificate(
    vault_id: str,
    token: str = Query(..., description="Access token from the webhook URL"),
    db: Session = Depends(get_db),
) -> dict:
    vault = get_vault_certificate(db, vault_id, token)
    if not vault:
        raise HTTPException(status_code=404, detail="Certificate not found or token invalid")
    payload = json.loads(vault.payload_json)
    serials = json.loads(vault.serial_numbers_json) if vault.serial_numbers_json else []
    return {
        "id": vault.id,
        "kind": vault.kind,
        "certificate_number": vault.certificate_number,
        "source": vault.source,
        "source_url": vault.source_url,
        "batch_id": vault.batch_id,
        "serial_numbers": serials,
        "retention_until": vault.retention_until.isoformat() if vault.retention_until else None,
        "payload": payload,
    }
