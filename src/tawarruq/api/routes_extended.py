from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session, joinedload

from tawarruq.api.deps import (
    require_manage_credentials,
    require_manage_institutions,
    require_tenant_access,
    tenant_filter_institution_id,
)
from tawarruq.database import get_db
from tawarruq.enums import ApiKeyRole, AuditActor, WebhookEvent
from tawarruq.models.application import FinancingApplication
from tawarruq.models.institution import Institution
from tawarruq.models.integration import WebhookSubscription
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.models.audit import AuditEvent
from tawarruq.schemas import (
    ApiClientRequestRead,
    ApiKeyRevealRequest,
    ApiKeyCreate,
    ApiKeyCreatedRead,
    ApiKeyRead,
    ApplicationRead,
    AuditEventRead,
    BusinessStatusRead,
    CustomerAgencyCreate,
    CustomerAgencyRead,
    CustomerSaleRead,
    ErrorResponse,
    HandoffCreate,
    HandoffRead,
    InstitutionRead,
    InstitutionUpdate,
    TransactionRead,
    WebhookCreate,
    WebhookCreatedRead,
    WebhookRead,
)
from tawarruq.schemas.kenya import ShariahAuditRead, ShariahIntegrityRead
from tawarruq.services.audit_query_service import export_audit_csv, query_audit_events
from tawarruq.services.audit_service import log_audit
from tawarruq.services.auth_service import create_api_key, list_api_keys
from tawarruq.services.rbac import can_issue_api_keys, get_request_role
from tawarruq.services.business_flow_service import (
    appoint_customer_agency,
    business_steps_ready_for_leg3,
    record_customer_sale,
    record_handoff,
)
from tawarruq.services.shariah_audit_service import query_shariah_audit_for_application, verify_application_shariah_integrity
from tawarruq.services.webhook_service import create_webhook, list_webhooks

router = APIRouter()

COMMON_ERRORS = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    404: {"model": ErrorResponse, "description": "Not found"},
}


@router.get("/institutions/{institution_id}", response_model=InstitutionRead, tags=["Institutions"])
def get_institution(institution_id: str, request: Request, db: Session = Depends(get_db)) -> InstitutionRead:
    require_tenant_access(request, institution_id)
    institution = db.get(Institution, institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    return institution


@router.patch("/institutions/{institution_id}", response_model=InstitutionRead, tags=["Institutions"])
def update_institution(
    institution_id: str, payload: InstitutionUpdate, request: Request, db: Session = Depends(get_db)
) -> InstitutionRead:
    require_manage_institutions(request)
    require_tenant_access(request, institution_id)
    institution = db.get(Institution, institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    try:
        from tawarruq.services.institution_service import update_institution as apply_institution_update

        apply_institution_update(
            db,
            institution,
            name=payload.name,
            bsas_mode=payload.bsas_mode,
            active=payload.active,
            approval_steps=payload.approval_steps,
            approval_limit_amount=payload.approval_limit_amount
            if "approval_limit_amount" in payload.model_fields_set
            else None,
            billing_fee_bps=payload.billing_fee_bps,
        )
        db.commit()
        db.refresh(institution)
        return institution
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/applications/{application_id}/customer-sale",
    response_model=CustomerSaleRead,
    status_code=201,
    tags=["Applications"],
    summary="Step 7: Record sale to customer",
)
def create_customer_sale(application_id: str, request: Request, db: Session = Depends(get_db)) -> CustomerSaleRead:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    try:
        sale = record_customer_sale(db, application_id, actor=AuditActor.HUMAN)
        db.commit()
        db.refresh(sale)
        return sale
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/applications/{application_id}/customer-agency",
    response_model=CustomerAgencyRead,
    status_code=201,
    tags=["Applications"],
    summary="Step 8: Appoint customer agency",
)
def create_customer_agency(
    application_id: str, payload: CustomerAgencyCreate, request: Request, db: Session = Depends(get_db)
) -> CustomerAgencyRead:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    try:
        agency = appoint_customer_agency(db, application_id, notes=payload.notes, actor=AuditActor.HUMAN)
        db.commit()
        db.refresh(agency)
        return agency
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/applications/{application_id}/business-status",
    response_model=BusinessStatusRead,
    tags=["Applications"],
)
def get_business_status(application_id: str, request: Request, db: Session = Depends(get_db)) -> BusinessStatusRead:
    application = (
        db.query(FinancingApplication)
        .options(
            joinedload(FinancingApplication.customer_sale),
            joinedload(FinancingApplication.customer_agency),
        )
        .filter(FinancingApplication.id == application_id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    return BusinessStatusRead(
        application_id=application.id,
        customer_sale_recorded=application.customer_sale is not None,
        customer_agency_appointed=application.customer_agency is not None,
        ready_for_leg_3=business_steps_ready_for_leg3(db, application.id),
    )


@router.get(
    "/applications/{application_id}/shariah-audit",
    response_model=list[ShariahAuditRead],
    tags=["Applications"],
    summary="Shariah audit trail for application",
)
def get_application_shariah_audit(
    application_id: str, request: Request, db: Session = Depends(get_db)
) -> list[ShariahAuditRead]:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    return query_shariah_audit_for_application(db, application_id)


@router.get(
    "/applications/{application_id}/shariah-audit/verify",
    response_model=ShariahIntegrityRead,
    tags=["Applications"],
    summary="Verify Shariah ledger integrity",
)
def verify_application_shariah_audit(
    application_id: str, request: Request, db: Session = Depends(get_db)
) -> ShariahIntegrityRead:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    result = verify_application_shariah_integrity(db, application_id)
    return ShariahIntegrityRead(**result)


@router.post("/webhooks", response_model=WebhookCreatedRead, status_code=201, tags=["Webhooks"])
def register_webhook(payload: WebhookCreate, request: Request, db: Session = Depends(get_db)) -> WebhookCreatedRead:
    require_manage_credentials(request)
    require_tenant_access(request, payload.institution_id)
    institution = db.get(Institution, payload.institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    sub, secret = create_webhook(db, institution_id=payload.institution_id, url=payload.url, events=payload.events)
    db.commit()
    db.refresh(sub)
    return WebhookCreatedRead(
        id=sub.id,
        institution_id=sub.institution_id,
        url=sub.url,
        events=sub.events,
        active=sub.active,
        created_at=sub.created_at,
        secret=secret,
    )


@router.get("/webhooks", response_model=list[WebhookRead], tags=["Webhooks"])
def get_webhooks(
    request: Request, institution_id: str | None = None, db: Session = Depends(get_db)
) -> list[WebhookRead]:
    scoped = tenant_filter_institution_id(request, institution_id)
    return list_webhooks(db, scoped)


@router.delete("/webhooks/{webhook_id}", status_code=204, tags=["Webhooks"])
def delete_webhook(webhook_id: str, request: Request, db: Session = Depends(get_db)) -> None:
    require_manage_credentials(request)
    sub = db.get(WebhookSubscription, webhook_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Webhook not found")
    require_tenant_access(request, sub.institution_id)
    sub.active = False
    db.commit()


@router.post(
    "/institutions/{institution_id}/api-keys",
    response_model=ApiKeyCreatedRead,
    status_code=201,
    tags=["Institutions"],
    summary="Create institution API key (Super Admin only)",
    description=(
        "Issues a machine key (prefer role api_client). When AUTH_ENABLED is on, only Super Admin "
        "can create keys. FI Admin should request BTI to onboard the institution key. The full key "
        "and HMAC secret are returned once."
    ),
)
def create_institution_api_key(
    institution_id: str, payload: ApiKeyCreate, request: Request, db: Session = Depends(get_db)
) -> ApiKeyCreatedRead:
    require_manage_credentials(request)
    require_tenant_access(request, institution_id)
    institution = db.get(Institution, institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    try:
        role = ApiKeyRole(payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid role: {payload.role}") from exc
    from tawarruq.services.rbac import (
        API_KEY_ALLOWED_ROLES,
        auth_is_enabled,
        can_cross_tenant,
        can_issue_api_keys,
    )

    if auth_is_enabled(request) and not can_issue_api_keys(request):
        raise HTTPException(
            status_code=403,
            detail="Only Super Admin can create API keys. On a managed install, request BTI to onboard the institution key.",
        )
    if role not in API_KEY_ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role {role.value} is not valid for API keys (use api_client for machine clients)",
        )
    if role == ApiKeyRole.PLATFORM_ADMIN and not can_cross_tenant(request):
        raise HTTPException(status_code=403, detail="Only platform admins can create platform_admin keys")
    record, raw_key = create_api_key(db, institution_id=institution_id, name=payload.name, role=role)
    db.commit()
    db.refresh(record)
    return ApiKeyCreatedRead(
        id=record.id,
        institution_id=record.institution_id,
        name=record.name,
        key_prefix=record.key_prefix,
        role=record.role,
        active=record.active,
        created_at=record.created_at,
        api_key=raw_key,
        hmac_secret=record.hmac_secret,
    )


@router.get(
    "/institutions/{institution_id}/api-keys",
    response_model=list[ApiKeyRead],
    tags=["Institutions"],
    summary="List institution API keys",
    description="Prefixes only. Creating keys is Super Admin only; this list is available to callers with tenant access.",
)
def get_institution_api_keys(
    institution_id: str, request: Request, db: Session = Depends(get_db)
) -> list[ApiKeyRead]:
    require_tenant_access(request, institution_id)
    return list_api_keys(db, institution_id)


API_CLIENT_REQUEST_ACTION = "institution.api_client.requested"


def _api_client_request_state(
    db: Session, institution_id: str, *, include_secrets: bool = False
) -> ApiClientRequestRead:
    keys = [key for key in list_api_keys(db, institution_id) if key.role == ApiKeyRole.API_CLIENT.value]
    latest = max(keys, key=lambda key: key.created_at) if keys else None
    last = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_id == institution_id, AuditEvent.action == API_CLIENT_REQUEST_ACTION)
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )
    if latest:
        status = "issued"
        if latest.reveal_key:
            message = "API client issued. Copy the key and HMAC secret for your core banking integration."
        else:
            message = "API client issued. The full key is not stored for this older key. Ask Super Admin to issue a new one."
    elif last:
        status = "requested"
        message = "Pending Super Admin. You will see the key here after it is issued."
    else:
        status = "none"
        message = "No API client requested yet."
    return ApiClientRequestRead(
        institution_id=institution_id,
        status=status,
        message=message,
        requested_at=last.timestamp if last else None,
        issued_at=latest.created_at if latest else None,
        key_count=len(keys),
        key_prefix=latest.key_prefix if latest else None,
        api_key=latest.reveal_key if latest and include_secrets else None,
        hmac_secret=latest.hmac_secret if latest and include_secrets else None,
    )


@router.get(
    "/institutions/{institution_id}/api-keys/request",
    response_model=ApiClientRequestRead,
    tags=["Institutions"],
    summary="API client request status",
)
def get_api_client_request(
    institution_id: str, request: Request, db: Session = Depends(get_db)
) -> ApiClientRequestRead:
    require_tenant_access(request, institution_id)
    institution = db.get(Institution, institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    return _api_client_request_state(db, institution_id)


@router.post(
    "/institutions/{institution_id}/api-keys/request",
    response_model=ApiClientRequestRead,
    tags=["Institutions"],
    summary="FI Admin request an API client key",
)
def request_api_client(
    institution_id: str, request: Request, db: Session = Depends(get_db)
) -> ApiClientRequestRead:
    require_manage_credentials(request)
    require_tenant_access(request, institution_id)
    if can_issue_api_keys(request):
        raise HTTPException(status_code=400, detail="Issue the API client key from Webhooks. You do not need to request it.")
    if get_request_role(request) != ApiKeyRole.INSTITUTION_ADMIN:
        raise HTTPException(status_code=403, detail="Only FI Admin can request an API client")
    institution = db.get(Institution, institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    if institution.lifecycle_status != "active" or not institution.active:
        raise HTTPException(status_code=400, detail="Request an API client only after this financial institution is active")
    current = _api_client_request_state(db, institution_id)
    if current.status == "issued":
        raise HTTPException(status_code=400, detail=current.message)
    if current.status == "requested":
        return current
    log_audit(
        db,
        entity_type="institution",
        entity_id=institution.id,
        actor=AuditActor.HUMAN,
        action=API_CLIENT_REQUEST_ACTION,
        details=f"code={institution.code}",
        institution_id=institution.id,
        actor_user_id=getattr(request.state, "ops_user_id", None),
        action_group="institutions",
    )
    db.commit()
    return _api_client_request_state(db, institution_id)


@router.post(
    "/institutions/{institution_id}/api-keys/reveal",
    response_model=ApiClientRequestRead,
    tags=["Institutions"],
    summary="Reveal issued API client secrets after password re-entry",
)
def reveal_api_client(
    institution_id: str, payload: ApiKeyRevealRequest, request: Request, db: Session = Depends(get_db)
) -> ApiClientRequestRead:
    require_tenant_access(request, institution_id)
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required to reveal the API client key")
    from tawarruq.models.ops_user import OpsUser
    from tawarruq.services.ops_user_service import verify_password

    user = db.get(OpsUser, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect password")
    institution = db.get(Institution, institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    current = _api_client_request_state(db, institution_id, include_secrets=True)
    if current.status != "issued":
        raise HTTPException(status_code=400, detail=current.message)
    if not current.api_key:
        raise HTTPException(status_code=400, detail=current.message)
    return current


@router.post("/handoffs", response_model=HandoffRead, status_code=201, tags=["Audit"])
def create_handoff(payload: HandoffCreate, db: Session = Depends(get_db)) -> HandoffRead:
    handoff = record_handoff(
        db,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        reason=payload.reason,
        assigned_to=payload.assigned_to,
        channel=payload.channel,
        actor=AuditActor.HUMAN,
    )
    db.commit()
    db.refresh(handoff)
    return handoff


@router.get("/audit/export", tags=["Audit"])
def export_audit(
    request: Request,
    entity_id: str | None = None,
    entity_type: str | None = None,
    actor: str | None = None,
    institution_id: str | None = None,
    format: str = Query("csv", pattern="^(csv)$"),
    db: Session = Depends(get_db),
) -> Response:
    from tawarruq.api.deps import require_export_data

    require_export_data(request)
    scoped = tenant_filter_institution_id(request, institution_id)
    events = query_audit_events(
        db,
        entity_id=entity_id,
        entity_type=entity_type,
        actor=actor,
        institution_id=scoped,
        limit=5000,
    )
    if format == "csv":
        content = export_audit_csv(events)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
        )
    raise HTTPException(status_code=400, detail="Unsupported format")
