import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from tawarruq.config import get_settings
from tawarruq.database import SessionLocal
from tawarruq.enums import ApiKeyRole
from tawarruq.models.mobile_account import MobileAccount
from tawarruq.models.ops_user import OpsUser
from tawarruq.services.auth_service import validate_api_key
from tawarruq.services.mobile_auth_service import decode_mobile_access_token
from tawarruq.services.ops_user_service import decode_session_token
from tawarruq.services.rbac import WRITE_BLOCKED_ROLES

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {"/health", "/metrics", "/docs", "/redoc", "/openapi.json", "/"}
PUBLIC_API_PATHS = {
    "/api/v1/ops/auth/login",
    "/api/v1/mobile/auth/register",
    "/api/v1/mobile/auth/verify-email",
    "/api/v1/mobile/auth/resend-verification",
    "/api/v1/mobile/auth/login",
    "/api/v1/mobile/auth/mfa",
    "/api/v1/mobile/auth/refresh",
    "/api/v1/mobile/auth/forgot-password",
    "/api/v1/mobile/auth/reset-password",
}
READ_METHODS = {"GET", "HEAD", "OPTIONS"}
PASSWORD_CHANGE_ALLOWED = {
    "/api/v1/ops/auth/change-password",
    "/api/v1/ops/auth/me",
    "/api/v1/ops/auth/login",
}
DEALER_ALLOWED_PREFIXES = (
    "/api/v1/ops/auth/me",
    "/api/v1/ops/auth/change-password",
    "/api/v1/ops/auth/login",
    "/api/v1/kenya/agent-dealers",
)


def _dealer_path_allowed(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") or path.startswith(prefix) for prefix in DEALER_ALLOWED_PREFIXES)


def _is_public_callback_path(path: str) -> bool:
    return "/kenya/callbacks/" in path


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _bind_mobile_session(request: Request, bearer: str) -> JSONResponse | None:
    """Attach mobile account to request.state. Returns error response if invalid."""
    mobile_payload = decode_mobile_access_token(bearer)
    if not mobile_payload:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired mobile session"})
    db = SessionLocal()
    try:
        account = db.get(MobileAccount, mobile_payload.get("sub"))
        if not account or not account.active:
            return JSONResponse(status_code=401, content={"detail": "Account inactive or missing"})
        request.state.mobile_account_id = account.id
        request.state.customer_id = account.customer_id
        request.state.institution_id = account.institution_id
        request.state.auth_method = "mobile"
    finally:
        db.close()
    return None


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path
        request.state.auth_enabled = settings.auth_enabled
        request.state.auth_method = None

        # Let CORSMiddleware answer browser preflight without auth.
        if request.method == "OPTIONS":
            return await call_next(request)

        if _is_public_callback_path(path) and settings.callback_auth_token:
            token = request.headers.get(settings.callback_auth_header)
            if token != settings.callback_auth_token:
                return JSONResponse(status_code=401, content={"detail": "Invalid callback token"})

        # Mobile auth works even when portal AUTH_ENABLED=false
        if path in PUBLIC_API_PATHS and path.startswith("/api/v1/mobile/"):
            return await call_next(request)

        if not settings.auth_enabled:
            bearer = _bearer_token(request)
            if bearer and path.startswith("/api/v1/mobile/"):
                err = _bind_mobile_session(request, bearer)
                if err:
                    return err
            return await call_next(request)

        if path in PUBLIC_PATHS or path in PUBLIC_API_PATHS or path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/api/v1/customer"):
            return await call_next(request)

        if path.startswith("/api/v1/tawarruq/certificates/"):
            return await call_next(request)

        if _is_public_callback_path(path):
            return await call_next(request)

        bearer = _bearer_token(request)
        if bearer:
            # Prefer mobile token when typ=mobile
            if decode_mobile_access_token(bearer):
                err = _bind_mobile_session(request, bearer)
                if err:
                    return err
                if not (path.startswith("/api/v1/mobile/") or path.startswith("/api/v1/kenya/")):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Mobile session cannot access this resource"},
                    )
                return await call_next(request)

            payload = decode_session_token(bearer)
            if not payload:
                return JSONResponse(status_code=401, content={"detail": "Invalid or expired session"})
            db = SessionLocal()
            try:
                user = db.get(OpsUser, payload.get("sub"))
                if not user or not user.active:
                    return JSONResponse(status_code=401, content={"detail": "User inactive or missing"})
                request.state.ops_user_id = user.id
                request.state.institution_id = user.institution_id
                request.state.agent_dealer_id = user.agent_dealer_id
                request.state.api_key_role = user.role
                request.state.is_platform_admin = user.role == ApiKeyRole.PLATFORM_ADMIN.value
                request.state.must_change_password = user.must_change_password
                request.state.auth_method = "session"
                if user.role == ApiKeyRole.AGENT_DEALER.value and not _dealer_path_allowed(path):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Agent dealers can only open their float desk"},
                    )
                if user.must_change_password and path not in PASSWORD_CHANGE_ALLOWED:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Password change required before using the portal"},
                    )
                if (
                    user.role in {role.value for role in WRITE_BLOCKED_ROLES}
                    and request.method not in READ_METHODS
                    and path not in PASSWORD_CHANGE_ALLOWED
                ):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "This role cannot perform write operations"},
                    )
            finally:
                db.close()
            return await call_next(request)

        header_name = settings.api_key_header
        raw_key = request.headers.get(header_name)
        if not raw_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization Bearer token or X-API-Key header"},
            )

        db = SessionLocal()
        try:
            record = validate_api_key(db, raw_key)
            if not record:
                return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
            request.state.institution_id = record.institution_id
            request.state.api_key_id = record.id
            request.state.api_key_role = record.role
            request.state.is_platform_admin = record.role == ApiKeyRole.PLATFORM_ADMIN.value
            request.state.auth_method = "api_key"
        finally:
            db.close()

        if record.role in {role.value for role in WRITE_BLOCKED_ROLES} and request.method not in READ_METHODS:
            return JSONResponse(
                status_code=403,
                content={"detail": "This role cannot perform write operations"},
            )

        return await call_next(request)
