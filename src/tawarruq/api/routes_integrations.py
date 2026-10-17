from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from tawarruq.api.deps import require_manage_integrations, require_tenant_access
from tawarruq.database import get_db
from tawarruq.models.institution import Institution
from tawarruq.models.institution_integration import InstitutionIntegration
from tawarruq.schemas.integrations import (
    InstitutionIntegrationRead,
    InstitutionIntegrationStatusRead,
    InstitutionIntegrationUpdate,
)
from tawarruq.services.callback_service import (
    handle_mno_possession_callback,
    handle_mpesa_b2c_result,
    handle_mpesa_stk_callback,
)
from tawarruq.services.integration_config_service import (
    get_institution_callback_urls,
    integration_status,
    upsert_institution_integration,
)

router = APIRouter()


def _to_read(record: InstitutionIntegration) -> InstitutionIntegrationRead:
    return InstitutionIntegrationRead(
        institution_id=record.institution_id,
        kenya_mode=record.kenya_mode,
        callback_base_url=record.callback_base_url,
        mpesa_env=record.mpesa_env,
        mpesa_shortcode=record.mpesa_shortcode,
        mpesa_initiator_name=record.mpesa_initiator_name,
        mpesa_b2c_command_id=record.mpesa_b2c_command_id,
        mno_safaricom_api_url=record.mno_safaricom_api_url,
        mno_safaricom_dealer_code=record.mno_safaricom_dealer_code,
        mno_airtel_api_url=record.mno_airtel_api_url,
        mno_airtel_token_url=record.mno_airtel_token_url,
        mno_airtel_client_id=record.mno_airtel_client_id,
        active=record.active,
        mpesa_consumer_key_set=bool(record.mpesa_consumer_key),
        mpesa_consumer_secret_set=bool(record.mpesa_consumer_secret),
        mpesa_security_credential_set=bool(record.mpesa_security_credential),
        mpesa_stk_passkey_set=bool(record.mpesa_stk_passkey),
        mno_safaricom_api_key_set=bool(record.mno_safaricom_api_key),
        mno_airtel_client_secret_set=bool(record.mno_airtel_client_secret),
    )


@router.get(
    "/institutions/{institution_id}/integrations",
    response_model=InstitutionIntegrationRead,
    tags=["Institution Integrations"],
    summary="Get institution integration config (secrets masked)",
)
def get_institution_integration(
    institution_id: str, request: Request, db: Session = Depends(get_db)
) -> InstitutionIntegrationRead:
    require_tenant_access(request, institution_id)
    if not db.get(Institution, institution_id):
        raise HTTPException(status_code=404, detail="Institution not found")
    record = db.query(InstitutionIntegration).filter(InstitutionIntegration.institution_id == institution_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Integration config not found — PUT to create")
    return _to_read(record)


@router.put(
    "/institutions/{institution_id}/integrations",
    response_model=InstitutionIntegrationRead,
    tags=["Institution Integrations"],
    summary="Create or update institution Daraja / MNO credentials",
)
def put_institution_integration(
    institution_id: str,
    payload: InstitutionIntegrationUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> InstitutionIntegrationRead:
    require_manage_integrations(request)
    require_tenant_access(request, institution_id)
    try:
        record = upsert_institution_integration(
            db, institution_id, payload.model_dump(exclude_unset=True)
        )
        db.commit()
        db.refresh(record)
        return _to_read(record)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/institutions/{institution_id}/integrations/status",
    response_model=InstitutionIntegrationStatusRead,
    tags=["Institution Integrations"],
    summary="Integration readiness + Daraja callback URLs to register",
)
def get_integration_status(institution_id: str, db: Session = Depends(get_db)) -> InstitutionIntegrationStatusRead:
    if not db.get(Institution, institution_id):
        raise HTTPException(status_code=404, detail="Institution not found")
    try:
        status = integration_status(db, institution_id)
        return InstitutionIntegrationStatusRead(**status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/institutions/{institution_id}/integrations/callback-urls",
    tags=["Institution Integrations"],
    summary="Daraja / MNO callback URLs for this institution",
)
def get_callback_urls(institution_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        return get_institution_callback_urls(db, institution_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# Institution-scoped callback routes (register these in each bank's Daraja portal)

@router.post(
    "/kenya/callbacks/{institution_id}/mpesa/b2c/result",
    tags=["Kenya Callbacks"],
    summary="Institution-scoped Daraja B2C ResultURL",
)
async def institution_mpesa_b2c_result(
    institution_id: str, request: Request, db: Session = Depends(get_db)
):
    if not db.get(Institution, institution_id):
        raise HTTPException(status_code=404, detail="Institution not found")
    body = await request.json()
    result = handle_mpesa_b2c_result(db, body)
    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted", "institution_id": institution_id, **result}


@router.post(
    "/kenya/callbacks/{institution_id}/mpesa/b2c/timeout",
    tags=["Kenya Callbacks"],
)
async def institution_mpesa_b2c_timeout(
    institution_id: str, request: Request, db: Session = Depends(get_db)
):
    if not db.get(Institution, institution_id):
        raise HTTPException(status_code=404, detail="Institution not found")
    body = await request.json()
    result = handle_mpesa_b2c_result(db, body)
    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted", "institution_id": institution_id, **result}


@router.post(
    "/kenya/callbacks/{institution_id}/mpesa/stk",
    tags=["Kenya Callbacks"],
    summary="Institution-scoped Daraja STK callback",
)
async def institution_mpesa_stk_callback(
    institution_id: str, request: Request, db: Session = Depends(get_db)
):
    if not db.get(Institution, institution_id):
        raise HTTPException(status_code=404, detail="Institution not found")
    body = await request.json()
    result = handle_mpesa_stk_callback(db, body)
    db.commit()
    return {"institution_id": institution_id, **result}


@router.post(
    "/kenya/callbacks/{institution_id}/mno/possession",
    tags=["Kenya Callbacks"],
    summary="Institution-scoped MNO possession webhook",
)
async def institution_mno_possession_callback(
    institution_id: str, request: Request, db: Session = Depends(get_db)
):
    if not db.get(Institution, institution_id):
        raise HTTPException(status_code=404, detail="Institution not found")
    body = await request.json()
    result = handle_mno_possession_callback(db, body)
    db.commit()
    return {"institution_id": institution_id, **result}
