"""FastAPI dependencies for multi-tenant institution scoping and RBAC."""

from fastapi import HTTPException, Request

from tawarruq.services.rbac import can_cross_tenant, get_request_role, has_permission, require_permission


def get_tenant_institution_id(request: Request) -> str | None:
    return getattr(request.state, "institution_id", None)


def require_tenant_access(request: Request, resource_institution_id: str) -> None:
    if can_cross_tenant(request):
        return
    tenant_id = get_tenant_institution_id(request)
    if tenant_id and tenant_id != resource_institution_id:
        raise HTTPException(status_code=403, detail="Access denied for this institution")


def tenant_filter_institution_id(request: Request, query_institution_id: str | None) -> str | None:
    """When auth is on, force queries to the API key's institution unless platform admin."""
    if can_cross_tenant(request):
        return query_institution_id
    tenant_id = get_tenant_institution_id(request)
    if tenant_id:
        return tenant_id
    return query_institution_id


def resolve_write_institution_id(request: Request, requested_institution_id: str | None) -> str | None:
    """Bind creates to the caller's tenant. Platform admin may choose any institution."""
    if can_cross_tenant(request):
        return requested_institution_id
    tenant_id = get_tenant_institution_id(request)
    if requested_institution_id and tenant_id and requested_institution_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied for this institution")
    return tenant_id or requested_institution_id


def require_write_ops(request: Request) -> None:
    require_permission(request, "write_ops")


def require_manage_credentials(request: Request) -> None:
    require_permission(request, "manage_credentials")


def require_manage_integrations(request: Request) -> None:
    require_permission(request, "manage_integrations")


def require_manage_institutions(request: Request) -> None:
    require_permission(request, "manage_institutions")


def get_auth_role(request: Request):
    return get_request_role(request)


def is_read_only(request: Request) -> bool:
    role = get_request_role(request)
    if role is None:
        return False
    from tawarruq.enums import ApiKeyRole

    return role == ApiKeyRole.READ_ONLY and getattr(request.state, "auth_enabled", False)
