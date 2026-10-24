"""HTTP middleware that writes grouped ops audit events for mutating / auth calls."""

from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from tawarruq.database import SessionLocal
from tawarruq.enums import AuditActor
from tawarruq.services.audit_service import classify_action_group, log_audit

logger = logging.getLogger(__name__)

SKIP_PREFIXES = (
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon",
)
SKIP_EXACT = {"/"}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# Auth endpoints are often public (no session yet) but must still be audited.
AUTH_SUFFIXES = (
    "/ops/auth/login",
    "/ops/auth/mfa",
    "/ops/auth/change-password",
    "/ops/auth/mfa/enroll",
    "/ops/auth/mfa/confirm",
    "/ops/auth/mfa/enable",
    "/ops/auth/mfa/disable",
    "/ops/auth/mfa/email/enable",
    "/ops/auth/mfa/email/send",
    "/ops/auth/mfa/email/confirm",
    "/mobile/auth/login",
    "/mobile/auth/register",
    "/mobile/auth/mfa",
)


def _should_audit(method: str, path: str) -> bool:
    if path in SKIP_EXACT or any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False
    if not path.startswith("/api/"):
        return False
    if method in MUTATING:
        return True
    return any(path.endswith(suffix) or suffix in path for suffix in AUTH_SUFFIXES)


def _action_for(method: str, path: str, status: int) -> str:
    if "/ops/auth/login" in path:
        return "auth.login_ok" if status < 400 else "auth.login_failed"
    if "/ops/auth/mfa" in path and method == "POST":
        return "auth.mfa_ok" if status < 400 else "auth.mfa_failed"
    if "/ops/auth/change-password" in path:
        return "auth.password_changed" if status < 400 else "auth.password_change_failed"
    if status >= 500:
        return f"http.{method.lower()}.error"
    if status >= 400:
        return f"http.{method.lower()}.rejected"
    return f"http.{method.lower()}"


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        group_id = str(uuid.uuid4())
        request.state.audit_group_id = group_id
        response = await call_next(request)

        path = request.url.path
        method = request.method.upper()
        status = getattr(response, "status_code", 500)
        if not _should_audit(method, path):
            return response

        try:
            self._persist(request, path=path, method=method, status=status, group_id=group_id)
        except Exception:
            logger.exception("Failed to persist HTTP audit event for %s %s", method, path)
        return response

    def _persist(self, request: Request, *, path: str, method: str, status: int, group_id: str) -> None:
        actor_user_id = getattr(request.state, "ops_user_id", None)
        institution_id = getattr(request.state, "institution_id", None)
        auth_method = getattr(request.state, "auth_method", None) or "anonymous"
        action = _action_for(method, path, status)
        action_group = classify_action_group(path, action)
        entity_type = "http_request"
        entity_id = actor_user_id or institution_id or group_id
        if "institution" in path and institution_id:
            entity_type = "institution"
            entity_id = institution_id
        elif actor_user_id and action_group in {"auth", "users"}:
            entity_type = "ops_user"
            entity_id = actor_user_id

        details = f"{method} {path} → {status} via {auth_method}"
        db = SessionLocal()
        try:
            log_audit(
                db,
                entity_type=entity_type,
                entity_id=entity_id,
                actor=AuditActor.HUMAN if actor_user_id else AuditActor.SYSTEM,
                action=action,
                details=details,
                institution_id=institution_id,
                actor_user_id=actor_user_id,
                group_id=group_id,
                action_group=action_group,
                http_method=method,
                http_path=path[:512],
                http_status=status,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
