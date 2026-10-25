"""Production ops endpoints: login, users, metrics, auth context."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tawarruq.api.deps import get_tenant_institution_id
from tawarruq.config import get_settings
from tawarruq.database import get_db
from tawarruq.enums import ApiKeyRole, AuditActor
from tawarruq.models.institution import Institution
from tawarruq.models.ops_user import OpsUser
from tawarruq.schemas import (
    AuditEventRead,
    AuditFeedRead,
    AuditGroupRead,
    AuthContextRead,
    OpsChangePasswordRequest,
    OpsLoginRequest,
    OpsLoginResponse,
    OpsMetricsRead,
    OpsProfileUpdate,
    OpsUserCreate,
    OpsUserCreatedRead,
    OpsUserPasswordResetRead,
    OpsUserPasswordResetRequest,
    OpsUserRead,
    OpsUserUpdate,
)
from tawarruq.services.audit_query_service import group_audit_events, query_audit_events
from tawarruq.services.audit_service import log_audit
from tawarruq.services.metrics_service import collect_ops_metrics

from tawarruq.services.ops_user_service import (
    authenticate_user,
    begin_mfa_enroll,
    change_password,
    confirm_email_mfa_enroll,
    confirm_mfa_enroll,
    create_mfa_challenge_token,
    create_ops_user,
    create_session_token,
    decode_mfa_challenge_token,
    delete_ops_user,
    deliver_ops_invite_email,
    disable_mfa,
    enable_email_mfa,
    enable_totp_mfa,
    issue_email_otp,
    list_ops_users,
    reset_ops_password,
    update_ops_user,
    user_mfa_method,
    verify_email_otp,
)
from tawarruq.services.totp_service import verify_totp
from tawarruq.services.rbac import (
    BTI_INTERNAL_ROLES,
    PLATFORM_SCOPED_ROLES,
    PRIVILEGED_MFA_ROLES,
    ROLE_PERMISSIONS,
    assert_may_invite,
    can_cross_tenant,
    get_request_role,
    has_permission,
    is_platform_admin,
    parse_role,
    require_permission,
)

router = APIRouter(tags=["Production Ops"])


class OpsMfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str = Field(..., min_length=6, max_length=8)


class OpsMfaConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8)


class OpsMfaDisableRequest(BaseModel):
    password: str = Field(..., min_length=8)


class UiAuditRequest(BaseModel):
    action: str = Field("ui.click", max_length=80)
    label: str = Field(..., max_length=160)
    path: str = Field(..., max_length=256)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return "unknown"


def _login_evidence(email: str, request: Request, *, mfa: str) -> str:
    return f"email={email.strip().lower()}; ip={_client_ip(request)}; mfa={mfa}"[:256]


def _mfa_enroll_required(user: OpsUser) -> bool:
    try:
        role = parse_role(user.role)
    except HTTPException:
        return False
    return role in PRIVILEGED_MFA_ROLES and not user.mfa_enabled


def _ops_login_payload(db: Session, user: OpsUser, *, require_mfa_challenge: bool = True) -> OpsLoginResponse:
    role = parse_role(user.role)
    method = user_mfa_method(user)
    if require_mfa_challenge and user.mfa_enabled:
        dev_code = None
        if method == "email":
            delivery = issue_email_otp(user, purpose="sign-in")
            dev_code = delivery.get("dev_code")
        return OpsLoginResponse(
            access_token="",
            role=user.role,
            email=user.email,
            full_name=user.full_name,
            institution_id=user.institution_id,
            institution_name=_institution_name(db, user.institution_id),
            agent_dealer_id=user.agent_dealer_id,
            must_change_password=user.must_change_password,
            permissions=[],
            mfa_required=True,
            mfa_token=create_mfa_challenge_token(user),
            mfa_enroll_required=False,
            mfa_enabled=True,
            mfa_method=method,
            mfa_dev_code=dev_code,
        )
    return OpsLoginResponse(
        access_token=create_session_token(user),
        role=user.role,
        email=user.email,
        full_name=user.full_name,
        institution_id=user.institution_id,
        institution_name=_institution_name(db, user.institution_id),
        agent_dealer_id=user.agent_dealer_id,
        must_change_password=user.must_change_password,
        permissions=_permissions_for_role(role),
        mfa_required=False,
        mfa_enroll_required=_mfa_enroll_required(user),
        mfa_enabled=bool(user.mfa_enabled),
        mfa_method=method,
    )


def _permissions_for_request(request: Request) -> list[str]:
    role = get_request_role(request)
    if role is None:
        return []
    return sorted(ROLE_PERMISSIONS.get(role, frozenset()))


def _permissions_for_role(role: ApiKeyRole) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, frozenset()))


def _institution_name(db: Session, institution_id: str | None) -> str | None:
    if not institution_id:
        return None
    institution = db.get(Institution, institution_id)
    return institution.name if institution else None


@router.post("/ops/auth/login", response_model=OpsLoginResponse, summary="Ops portal login")
def ops_login(payload: OpsLoginRequest, request: Request, db: Session = Depends(get_db)) -> OpsLoginResponse:
    settings = get_settings()
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth is disabled (AUTH_ENABLED=false)")
    group_id = getattr(request.state, "audit_group_id", None)
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        log_audit(
            db,
            entity_type="ops_user",
            entity_id=group_id or "login",
            actor=AuditActor.SYSTEM,
            action="auth.login_failed",
            details=f"email={payload.email.strip().lower()}",
            evidence_ref=_login_evidence(payload.email, request, mfa="none"),
            group_id=group_id,
            action_group="auth",
            http_method="POST",
            http_path="/api/v1/ops/auth/login",
            http_status=401,
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")
    log_audit(
        db,
        entity_type="ops_user",
        entity_id=user.id,
        actor=AuditActor.HUMAN,
        action="auth.login_ok",
        details=f"email={user.email}, role={user.role}",
        evidence_ref=_login_evidence(user.email, request, mfa="pending" if user.mfa_enabled else "none"),
        institution_id=user.institution_id,
        actor_user_id=user.id,
        group_id=group_id,
        action_group="auth",
        http_method="POST",
        http_path="/api/v1/ops/auth/login",
        http_status=200,
    )
    db.commit()
    return _ops_login_payload(db, user)


@router.post("/ops/auth/mfa", response_model=OpsLoginResponse, summary="Verify MFA code (authenticator or email)")
def ops_mfa_verify(payload: OpsMfaVerifyRequest, db: Session = Depends(get_db)) -> OpsLoginResponse:
    challenge = decode_mfa_challenge_token(payload.mfa_token)
    if not challenge:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA challenge")
    user = db.get(OpsUser, challenge.get("sub"))
    if not user or not user.active or not user.mfa_enabled:
        raise HTTPException(status_code=401, detail="User not found")
    method = user_mfa_method(user)
    if method == "email":
        if not verify_email_otp(user, payload.code):
            raise HTTPException(status_code=401, detail="Invalid or expired email code")
    else:
        if not user.mfa_secret or not verify_totp(user.mfa_secret, payload.code):
            raise HTTPException(status_code=401, detail="Invalid authenticator code")
    return _ops_login_payload(db, user, require_mfa_challenge=False)


@router.post("/ops/auth/mfa/enroll", summary="Start authenticator (TOTP) enrollment")
def ops_mfa_enroll(request: Request, db: Session = Depends(get_db)) -> dict:
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")
    user = db.get(OpsUser, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    secret, url = begin_mfa_enroll(user)
    db.commit()
    return {"secret": secret, "otpauth_url": url, "email": user.email, "method": "totp"}


@router.post("/ops/auth/mfa/confirm", response_model=OpsLoginResponse, summary="Confirm authenticator enrollment")
def ops_mfa_confirm(
    payload: OpsMfaConfirmRequest, request: Request, db: Session = Depends(get_db)
) -> OpsLoginResponse:
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")
    user = db.get(OpsUser, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    try:
        confirm_mfa_enroll(user, payload.code)
        db.commit()
        db.refresh(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ops_login_payload(db, user, require_mfa_challenge=False)


@router.post("/ops/auth/mfa/email/send", summary="Send email MFA enrollment or challenge code")
def ops_mfa_email_send(request: Request, db: Session = Depends(get_db)) -> dict:
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")
    user = db.get(OpsUser, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    delivery = issue_email_otp(user, purpose="MFA enrollment")
    return {
        "email": user.email,
        "smtp_sent": delivery["smtp_sent"],
        "mail_path": delivery["mail_path"],
        "dev_code": delivery["dev_code"],
        "method": "email",
    }


@router.post("/ops/auth/mfa/email/confirm", response_model=OpsLoginResponse, summary="Confirm email MFA enrollment")
def ops_mfa_email_confirm(
    payload: OpsMfaConfirmRequest, request: Request, db: Session = Depends(get_db)
) -> OpsLoginResponse:
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")
    user = db.get(OpsUser, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    try:
        confirm_email_mfa_enroll(user, payload.code)
        db.commit()
        db.refresh(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ops_login_payload(db, user, require_mfa_challenge=False)


@router.post("/ops/auth/mfa/email/enable", response_model=OpsLoginResponse, summary="Enable email MFA (codes gated at login)")
def ops_mfa_email_enable(request: Request, db: Session = Depends(get_db)) -> OpsLoginResponse:
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")
    user = db.get(OpsUser, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    enable_email_mfa(user)
    db.commit()
    db.refresh(user)
    return _ops_login_payload(db, user, require_mfa_challenge=False)


@router.post("/ops/auth/mfa/enable", response_model=OpsLoginResponse, summary="Enable authenticator MFA after QR setup")
def ops_mfa_enable(request: Request, db: Session = Depends(get_db)) -> OpsLoginResponse:
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")
    user = db.get(OpsUser, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    try:
        enable_totp_mfa(user)
        db.commit()
        db.refresh(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ops_login_payload(db, user, require_mfa_challenge=False)


@router.post("/ops/auth/mfa/disable", response_model=OpsLoginResponse, summary="Disable MFA (password required)")
def ops_mfa_disable(
    payload: OpsMfaDisableRequest, request: Request, db: Session = Depends(get_db)
) -> OpsLoginResponse:
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")
    user = db.get(OpsUser, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    try:
        role = parse_role(user.role)
        if role in PRIVILEGED_MFA_ROLES and user.mfa_enabled:
            # Privileged roles may disable only to re-enroll; still require password.
            pass
        disable_mfa(user, password=payload.password)
        db.commit()
        db.refresh(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ops_login_payload(db, user, require_mfa_challenge=False)


@router.post("/ops/auth/change-password", response_model=OpsLoginResponse, summary="Change password")
def ops_change_password(
    payload: OpsChangePasswordRequest, request: Request, db: Session = Depends(get_db)
) -> OpsLoginResponse:
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required to change password")
    user = db.get(OpsUser, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")
    try:
        change_password(
            db,
            user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
        db.commit()
        db.refresh(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ops_login_payload(db, user, require_mfa_challenge=False)


@router.get("/ops/auth/me", response_model=AuthContextRead, summary="Current auth context")
def auth_me(request: Request, db: Session = Depends(get_db)) -> AuthContextRead:
    settings = get_settings()
    role = get_request_role(request)
    institution_id = get_tenant_institution_id(request)
    user_id = getattr(request.state, "ops_user_id", None)
    email = None
    full_name = None
    must_change = False
    mfa_enabled = False
    mfa_enroll_required = False
    mfa_method = None
    job_title = None
    department = None
    employee_number = None
    phone = None
    office = None
    agent_dealer_id = getattr(request.state, "agent_dealer_id", None)
    if user_id:
        user = db.get(OpsUser, user_id)
        if user:
            email = user.email
            full_name = user.full_name
            must_change = user.must_change_password
            agent_dealer_id = user.agent_dealer_id
            mfa_enabled = bool(user.mfa_enabled)
            mfa_enroll_required = _mfa_enroll_required(user)
            mfa_method = user_mfa_method(user)
            job_title = user.job_title
            department = user.department
            employee_number = user.employee_number
            phone = user.phone
            office = user.office
    return AuthContextRead(
        auth_enabled=settings.auth_enabled,
        authenticated=role is not None or not settings.auth_enabled,
        role=role.value if role else None,
        institution_id=institution_id,
        institution_name=_institution_name(db, institution_id),
        is_platform_admin=can_cross_tenant(request) and settings.auth_enabled,
        permissions=_permissions_for_request(request),
        email=email,
        full_name=full_name,
        user_id=user_id,
        agent_dealer_id=agent_dealer_id,
        must_change_password=must_change,
        auth_method=getattr(request.state, "auth_method", None),
        mfa_enabled=mfa_enabled,
        mfa_enroll_required=mfa_enroll_required,
        mfa_method=mfa_method,
        job_title=job_title,
        department=department,
        employee_number=employee_number,
        phone=phone,
        office=office,
        deployment_mode=settings.normalized_mode,
        enabled_products=settings.products,
        brand_name=settings.brand_display,
    )


@router.patch(
    "/ops/auth/me",
    response_model=AuthContextRead,
    summary="Update own profile and HR fields",
)
def update_own_profile(
    payload: OpsProfileUpdate, request: Request, db: Session = Depends(get_db)
) -> AuthContextRead:
    user_id = getattr(request.state, "ops_user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in required")
    user = db.get(OpsUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        extra = {}
        for field in ("job_title", "department", "employee_number", "phone", "office", "full_name"):
            if field in payload.model_fields_set:
                extra[field] = getattr(payload, field)
        update_ops_user(
            db,
            user,
            actor_id=user_id,
            actor_is_platform_admin=can_cross_tenant(request),
            audit_action="ops_user.profile_updated",
            **extra,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return auth_me(request, db)


@router.get("/ops/auth/users", response_model=list[OpsUserRead], summary="List ops users")
def get_ops_users(request: Request, db: Session = Depends(get_db)) -> list[OpsUserRead]:
    require_permission(request, "manage_credentials")
    scoped = None if can_cross_tenant(request) else get_tenant_institution_id(request)
    return list_ops_users(db, institution_id=scoped)


@router.get(
    "/ops/auth/users/{user_id}",
    response_model=OpsUserRead,
    summary="Get one ops user for management",
)
def get_ops_user(user_id: str, request: Request, db: Session = Depends(get_db)) -> OpsUserRead:
    return _managed_user(request, db, user_id)


@router.post(
    "/ops/auth/users",
    response_model=OpsUserCreatedRead,
    status_code=201,
    summary="Invite ops user: create account, email temporary password via SMTP",
    description=(
        "Requires manage_credentials. Super Admin may invite platform_admin, institution_admin, "
        "bti_ops, shariah_officer, bti_finance, reconciler (not institution_ops or fi_approver). "
        "FI Admin may invite institution_admin, institution_ops, fi_approver, shariah_officer, "
        "reconciler for their own tenant. Tenant-scoped roles need institution_id when the caller "
        "is Super Admin."
    ),
)
def create_ops_user_endpoint(
    payload: OpsUserCreate, request: Request, db: Session = Depends(get_db)
) -> OpsUserCreatedRead:
    require_permission(request, "manage_credentials")
    try:
        role = ApiKeyRole(payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid role: {payload.role}") from exc

    assert_may_invite(request, role)

    institution_id = payload.institution_id
    if role in PLATFORM_SCOPED_ROLES:
        institution_id = None
    elif not can_cross_tenant(request):
        institution_id = get_tenant_institution_id(request)

    try:
        user, temp = create_ops_user(
            db,
            email=payload.email,
            full_name=payload.full_name,
            role=role,
            institution_id=institution_id,
            agent_dealer_id=payload.agent_dealer_id,
            approval_limit_amount=payload.approval_limit_amount,
            temporary_password=payload.temporary_password,
            created_by_id=getattr(request.state, "ops_user_id", None),
            must_change_password=True,
        )
        db.commit()
        db.refresh(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    delivery = deliver_ops_invite_email(user=user, temporary_password=temp, kind="invite")
    if delivery["smtp_sent"]:
        invite_message = (
            f"Invite emailed to {user.email}. They must change the temporary password on first login."
        )
    else:
        invite_message = (
            "User created. SMTP did not send — copy the temporary password below and share it securely. "
            "They must change it on first login."
        )

    base = OpsUserRead.model_validate(user)
    return OpsUserCreatedRead(
        **base.model_dump(),
        temporary_password=temp if delivery["expose_password"] else None,
        smtp_sent=bool(delivery["smtp_sent"]),
        mail_path=delivery.get("mail_path"),
        invite_message=invite_message,
    )


def _managed_user(request: Request, db: Session, user_id: str) -> OpsUser:
    require_permission(request, "manage_credentials")
    target = db.get(OpsUser, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if not can_cross_tenant(request):
        tenant_id = get_tenant_institution_id(request)
        if target.role in {r.value for r in BTI_INTERNAL_ROLES}:
            raise HTTPException(status_code=403, detail="Institution admins cannot manage BTI internal users")
        if target.role != ApiKeyRole.AGENT_DEALER.value and target.institution_id != tenant_id:
            raise HTTPException(status_code=403, detail="Access denied for this user")
    return target


@router.patch(
    "/ops/auth/users/{user_id}",
    response_model=OpsUserRead,
    summary="Update ops user name, role, institution, or active flag",
    description=(
        "Changing role uses the same invite rules as create: you cannot assign a role you are "
        "not allowed to invite."
    ),
)
def update_ops_user_endpoint(
    user_id: str, payload: OpsUserUpdate, request: Request, db: Session = Depends(get_db)
) -> OpsUserRead:
    target = _managed_user(request, db, user_id)
    role = None
    if payload.role is not None:
        try:
            role = ApiKeyRole(payload.role)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid role: {payload.role}") from exc
        assert_may_invite(request, role)
    institution_id = payload.institution_id
    next_role = role.value if role is not None else target.role
    if next_role in {r.value for r in PLATFORM_SCOPED_ROLES}:
        institution_id = None
    elif not can_cross_tenant(request):
        institution_id = get_tenant_institution_id(request)
    try:
        extra = {}
        for field in (
            "approval_limit_amount",
            "job_title",
            "department",
            "employee_number",
            "phone",
            "office",
        ):
            if field in payload.model_fields_set:
                extra[field] = getattr(payload, field)
        updated = update_ops_user(
            db,
            target,
            full_name=payload.full_name,
            email=payload.email,
            role=role,
            institution_id=institution_id,
            agent_dealer_id=payload.agent_dealer_id,
            active=payload.active,
            actor_id=getattr(request.state, "ops_user_id", None),
            actor_is_platform_admin=can_cross_tenant(request),
            **extra,
        )
        db.commit()
        db.refresh(updated)
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/ops/auth/users/{user_id}/reset-password",
    response_model=OpsUserPasswordResetRead,
    summary="Issue a new temporary password, email it via SMTP, force change on next login",
)
def reset_ops_user_password(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    payload: OpsUserPasswordResetRequest | None = None,
) -> OpsUserPasswordResetRead:
    target = _managed_user(request, db, user_id)
    try:
        temp = reset_ops_password(
            db,
            target,
            temporary_password=payload.temporary_password if payload else None,
        )
        db.commit()
        db.refresh(target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    delivery = deliver_ops_invite_email(user=target, temporary_password=temp, kind="reset")
    if delivery["smtp_sent"]:
        invite_message = (
            f"Temporary password emailed to {target.email}. They must change it on next login."
        )
    else:
        invite_message = (
            "Password reset. SMTP did not send — copy the temporary password below and share it securely."
        )

    return OpsUserPasswordResetRead(
        id=target.id,
        email=target.email,
        full_name=target.full_name,
        role=target.role,
        temporary_password=temp if delivery["expose_password"] else None,
        must_change_password=True,
        smtp_sent=bool(delivery["smtp_sent"]),
        mail_path=delivery.get("mail_path"),
        invite_message=invite_message,
    )


@router.delete(
    "/ops/auth/users/{user_id}",
    status_code=204,
    summary="Delete an ops user",
)
def delete_ops_user_endpoint(user_id: str, request: Request, db: Session = Depends(get_db)) -> None:
    target = _managed_user(request, db, user_id)
    try:
        delete_ops_user(db, target, actor_id=getattr(request.state, "ops_user_id", None))
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/ops/audit",
    response_model=AuditFeedRead,
    summary="Grouped ops audit feed",
    description=(
        "Super Admin / BTI cross-tenant roles see all institutions. "
        "Institution admins see only their tenant. Events are grouped by request id."
    ),
)
def ops_audit_feed(
    request: Request,
    db: Session = Depends(get_db),
    institution_id: str | None = None,
    action_group: str | None = None,
    actor_user_id: str | None = None,
    group_id: str | None = None,
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    limit: int = Query(300, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    grouped: bool = Query(True),
) -> AuditFeedRead:
    # Admins and ops desks that already see metrics / credentials / institutions.
    if not (
        has_permission(request, "manage_institutions")
        or has_permission(request, "manage_credentials")
        or has_permission(request, "view_metrics")
        or has_permission(request, "export_data")
    ):
        raise HTTPException(status_code=403, detail="Audit feed requires an admin or ops role")

    cross_tenant = can_cross_tenant(request)
    if cross_tenant:
        scoped = institution_id
    else:
        scoped = get_tenant_institution_id(request)
        if not scoped:
            raise HTTPException(status_code=403, detail="No institution scope for this login")
        if institution_id and institution_id != scoped:
            raise HTTPException(status_code=403, detail="Access denied for this institution")

    events = query_audit_events(
        db,
        institution_id=scoped,
        action_group=action_group,
        actor_user_id=actor_user_id,
        group_id=group_id,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
    )
    event_reads = [AuditEventRead.model_validate(event) for event in events]
    groups: list[AuditGroupRead] = []
    if grouped:
        for bucket in group_audit_events(events):
            groups.append(
                AuditGroupRead(
                    group_id=bucket["group_id"],
                    action_group=bucket["action_group"],
                    institution_id=bucket.get("institution_id"),
                    actor_user_id=bucket.get("actor_user_id"),
                    actor=bucket.get("actor"),
                    started_at=bucket.get("started_at"),
                    ended_at=bucket.get("ended_at"),
                    events=[AuditEventRead.model_validate(e) for e in bucket["events"]],
                )
            )
    return AuditFeedRead(
        scope_institution_id=scoped,
        cross_tenant=cross_tenant,
        groups=groups,
        events=event_reads,
    )


@router.post("/ops/audit/ui", status_code=204, summary="Record a portal control press")
def log_ui_audit(payload: UiAuditRequest, request: Request, db: Session = Depends(get_db)) -> Response:
    settings = get_settings()
    user_id = getattr(request.state, "ops_user_id", None)
    if settings.auth_enabled and not user_id:
        raise HTTPException(status_code=401, detail="Session required")
    label = payload.label.strip()[:160]
    path = payload.path.strip()[:256] or "/"
    action = (payload.action or "ui.click").strip()[:80] or "ui.click"
    log_audit(
        db,
        entity_type="ui",
        entity_id=user_id or "anonymous",
        actor=AuditActor.HUMAN,
        action=action,
        details=f"{label} {path}",
        evidence_ref=f"{label}; {path}"[:256],
        institution_id=getattr(request.state, "institution_id", None),
        actor_user_id=user_id,
        group_id=getattr(request.state, "audit_group_id", None),
        action_group="ui",
        http_method="POST",
        http_path="/api/v1/ops/audit/ui",
        http_status=204,
    )
    db.commit()
    return Response(status_code=204)


@router.get("/ops/metrics", response_model=OpsMetricsRead, summary="Operational metrics dashboard")
def ops_metrics(request: Request, db: Session = Depends(get_db)) -> OpsMetricsRead:
    require_permission(request, "view_metrics")
    settings = get_settings()
    institution_id = None if can_cross_tenant(request) else get_tenant_institution_id(request)
    data = collect_ops_metrics(db, settings, institution_id=institution_id)
    return OpsMetricsRead(**data)
