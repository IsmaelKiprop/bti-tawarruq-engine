"""Role-based access control for API keys and ops portal sessions."""

from fastapi import HTTPException, Request

from tawarruq.enums import ApiKeyRole

# Permissions are stable strings; roles compose them (BTI users doc §5).
ROLE_PERMISSIONS: dict[ApiKeyRole, frozenset[str]] = {
    ApiKeyRole.PLATFORM_ADMIN: frozenset(
        {
            "read",
            "write_bti_ops",
            "manage_credentials",
            "manage_integrations",
            "manage_institutions",
            "manage_billing",
            "reconcile",
            "view_metrics",
            "view_shariah",
            "export_data",
            "api_submit",
        }
    ),
    ApiKeyRole.BTI_OPS: frozenset(
        {
            "read",
            "write_ops",
            "write_bti_ops",
            "view_metrics",
            "view_shariah",
            "export_data",
        }
    ),
    ApiKeyRole.BTI_FINANCE: frozenset(
        {
            "read",
            "manage_billing",
            "view_metrics",
            "export_data",
        }
    ),
    ApiKeyRole.INSTITUTION_ADMIN: frozenset(
        {
            "read",
            "write_ops",
            "approve_txn",
            "manage_credentials",
            "manage_integrations",
            "view_metrics",
            "view_shariah",
            "export_data",
        }
    ),
    ApiKeyRole.INSTITUTION_OPS: frozenset(
        {
            "read",
            "write_ops",
            "view_metrics",
            "view_shariah",
        }
    ),
    ApiKeyRole.FI_APPROVER: frozenset(
        {
            "read",
            "approve_txn",
            "view_metrics",
        }
    ),
    ApiKeyRole.SHARIAH_OFFICER: frozenset({"read", "view_metrics", "view_shariah", "export_data"}),
    ApiKeyRole.RECONCILER: frozenset({"read", "reconcile", "view_metrics", "export_data"}),
    ApiKeyRole.READ_ONLY: frozenset({"read", "view_metrics"}),
    ApiKeyRole.AGENT_DEALER: frozenset({"dealer_desk"}),
    ApiKeyRole.API_CLIENT: frozenset({"read", "api_submit", "write_ops", "view_metrics"}),
}

# Blocked from arbitrary HTTP writes at middleware (dedicated paths remain open).
WRITE_BLOCKED_ROLES = {
    ApiKeyRole.READ_ONLY,
    ApiKeyRole.SHARIAH_OFFICER,
    ApiKeyRole.BTI_FINANCE,
    ApiKeyRole.RECONCILER,
    ApiKeyRole.FI_APPROVER,
}

PRIVILEGED_MFA_ROLES = {
    ApiKeyRole.PLATFORM_ADMIN,
    ApiKeyRole.BTI_OPS,
    ApiKeyRole.BTI_FINANCE,
}

# Portal logins — API_CLIENT is machine-only.
PORTAL_ASSIGNABLE_ROLES = frozenset(
    {
        ApiKeyRole.PLATFORM_ADMIN,
        ApiKeyRole.BTI_OPS,
        ApiKeyRole.BTI_FINANCE,
        ApiKeyRole.INSTITUTION_ADMIN,
        ApiKeyRole.INSTITUTION_OPS,
        ApiKeyRole.FI_APPROVER,
        ApiKeyRole.SHARIAH_OFFICER,
        ApiKeyRole.RECONCILER,
        ApiKeyRole.READ_ONLY,
        ApiKeyRole.AGENT_DEALER,
    }
)

# Only platform_admin may assign these BTI-internal roles.
BTI_INTERNAL_ROLES = frozenset(
    {
        ApiKeyRole.PLATFORM_ADMIN,
        ApiKeyRole.BTI_OPS,
        ApiKeyRole.BTI_FINANCE,
    }
)

# No institution_id required (platform-scoped humans).
PLATFORM_SCOPED_ROLES = frozenset(
    {
        ApiKeyRole.PLATFORM_ADMIN,
        ApiKeyRole.BTI_OPS,
        ApiKeyRole.BTI_FINANCE,
        ApiKeyRole.AGENT_DEALER,
    }
)

# Roles that may see across tenants when institution_id is unbound (or always for BTI ops/finance).
CROSS_TENANT_ROLES = frozenset(
    {
        ApiKeyRole.PLATFORM_ADMIN,
        ApiKeyRole.BTI_OPS,
        ApiKeyRole.BTI_FINANCE,
    }
)

API_KEY_ALLOWED_ROLES = frozenset(
    {
        ApiKeyRole.PLATFORM_ADMIN,
        ApiKeyRole.INSTITUTION_ADMIN,
        ApiKeyRole.INSTITUTION_OPS,
        ApiKeyRole.SHARIAH_OFFICER,
        ApiKeyRole.READ_ONLY,
        ApiKeyRole.API_CLIENT,
        ApiKeyRole.BTI_OPS,
    }
)


def parse_role(raw: str | None) -> ApiKeyRole:
    if not raw:
        return ApiKeyRole.INSTITUTION_OPS
    try:
        return ApiKeyRole(raw)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f"Unknown API key role: {raw}") from exc


def get_request_role(request: Request) -> ApiKeyRole | None:
    raw = getattr(request.state, "api_key_role", None)
    if raw is None:
        return None
    return parse_role(raw)


def is_platform_admin(request: Request) -> bool:
    return getattr(request.state, "is_platform_admin", False)


def auth_is_enabled(request: Request) -> bool:
    return getattr(request.state, "auth_enabled", False)


def has_permission(request: Request, permission: str) -> bool:
    if not auth_is_enabled(request):
        return True
    role = get_request_role(request)
    if role is None:
        return False
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def require_permission(request: Request, permission: str) -> None:
    if has_permission(request, permission):
        return
    role = get_request_role(request)
    raise HTTPException(
        status_code=403,
        detail=f"Permission denied: {permission} required (role={role.value if role else 'none'})",
    )


def can_cross_tenant(request: Request) -> bool:
    if not auth_is_enabled(request):
        return True
    if is_platform_admin(request):
        return True
    role = get_request_role(request)
    if role in CROSS_TENANT_ROLES:
        return True
    # BTI-wide reconciler (no institution bind) may scan across tenants.
    if role == ApiKeyRole.RECONCILER and not getattr(request.state, "institution_id", None):
        return True
    return False
