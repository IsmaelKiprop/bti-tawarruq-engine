"""Role-based access control for API keys."""

from fastapi import HTTPException, Request

from tawarruq.enums import ApiKeyRole

ROLE_PERMISSIONS: dict[ApiKeyRole, frozenset[str]] = {
    ApiKeyRole.PLATFORM_ADMIN: frozenset(
        {
            "read",
            "write_ops",
            "manage_credentials",
            "manage_integrations",
            "manage_institutions",
            "view_metrics",
            "view_shariah",
        }
    ),
    ApiKeyRole.INSTITUTION_ADMIN: frozenset(
        {
            "read",
            "write_ops",
            "manage_credentials",
            "manage_integrations",
            "view_metrics",
            "view_shariah",
        }
    ),
    ApiKeyRole.INSTITUTION_OPS: frozenset({"read", "write_ops", "view_metrics", "view_shariah"}),
    ApiKeyRole.AGENT_DEALER: frozenset({"dealer_desk"}),
    ApiKeyRole.SHARIAH_OFFICER: frozenset({"read", "view_metrics", "view_shariah"}),
    ApiKeyRole.READ_ONLY: frozenset({"read", "view_metrics"}),
}

WRITE_BLOCKED_ROLES = {ApiKeyRole.READ_ONLY, ApiKeyRole.SHARIAH_OFFICER}


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
    return is_platform_admin(request)
