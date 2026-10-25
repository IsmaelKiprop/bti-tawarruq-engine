import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse

from sqlalchemy import text

from tawarruq import __version__
from tawarruq.amanah.worker import AmanahWorker
from tawarruq.api.audit_middleware import AuditMiddleware
from tawarruq.api.middleware import ApiKeyMiddleware
from tawarruq.api.openapi_metadata import API_DESCRIPTION, OPENAPI_TAGS
from tawarruq.api.routes import router
from tawarruq.api.routes_callbacks import router as callbacks_router
from tawarruq.api.routes_customer import router as customer_router
from tawarruq.api.routes_extended import router as extended_router
from tawarruq.api.routes_integrations import router as integrations_router
from tawarruq.api.routes_kenya import router as kenya_router
from tawarruq.api.routes_manual_bridge import router as manual_bridge_router
from tawarruq.api.routes_ops import router as ops_router
from tawarruq.api.routes_ops_mobile import router as ops_mobile_router
from tawarruq.api.routes_mobile_auth import router as mobile_auth_router
from tawarruq.api.routes_controls import router as controls_router
from tawarruq.api.routes_sacco import router as sacco_router
from tawarruq.api.routes_sedania import router as sedania_router
from tawarruq.config import get_settings
from tawarruq.database import SessionLocal, init_db
from tawarruq.schemas import HealthRead
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.metrics_service import collect_ops_metrics, render_prometheus
from tawarruq.services.monitoring import RequestMetricsMiddleware

logger = logging.getLogger(__name__)
PROCESS_STARTED_AT = time.time()


def _attach_swagger_security(app: FastAPI) -> None:
    """Show Authorize in /docs so testers can paste a Bearer session or X-API-Key."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        schema.setdefault("components", {})
        schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Ops session. Login at POST /ops/auth/login, then paste access_token here.",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "Machine key. Super Admin creates these on POST /institutions/{id}/api-keys.",
            },
        }
        schema["security"] = [{"BearerAuth": []}, {"ApiKeyAuth": []}]
        public_suffixes = ("/ops/auth/login", "/ops/auth/mfa", "/health")
        for path, methods in schema.get("paths", {}).items():
            if any(path.endswith(suffix) for suffix in public_suffixes):
                for operation in methods.values():
                    if isinstance(operation, dict):
                        operation["security"] = []
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()

    from tawarruq.database import SessionLocal

    db = SessionLocal()
    try:
        get_or_create_default_institution(db)
        from tawarruq.services.seed_service import seed_kenya_defaults
        from tawarruq.services.ops_seed_service import seed_ops_role_catalogue

        seed_kenya_defaults(db)
        seeded = seed_ops_role_catalogue(db)
        db.commit()
        created = [row for row in seeded if row.created]
        if created:
            logger.warning(
                "Seeded %s ops catalogue identities — see data/ops_seed_credentials.txt; force password change on first login",
                len(created),
            )
    finally:
        db.close()

    task = None
    if settings.amanah_enabled:
        worker = AmanahWorker()
        task = asyncio.create_task(worker.run_forever())

    logger.info("Buruuj Tawarruq Engine started (v%s)", __version__)

    yield

    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    settings = get_settings()
    brand = settings.brand_display
    app = FastAPI(
        title=f"{brand} Tawarruq Engine API",
        description=API_DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
        contact={
            "name": brand,
            "url": "https://github.com/IsmaelKiprop/bti-tawarruq-engine",
        },
        license_info={"name": "Proprietary"},
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    _attach_swagger_security(app)

    # Inner middlewares first; CORS must be outermost so 401/403 still get ACAO headers.
    settings = get_settings()
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:15173",
        "http://localhost:15173",
    ]
    portal_origin = (settings.portal_public_url or "").rstrip("/")
    if portal_origin and portal_origin not in cors_origins:
        cors_origins.append(portal_origin)
    for origin in settings.extra_cors_origins:
        if origin not in cors_origins:
            cors_origins.append(origin)

    app.add_middleware(ApiKeyMiddleware)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RequestMetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=(
            r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
            r"|https://([a-z0-9-]+\.)?buruujfintech\.com"
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _database_ok() -> bool:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("Database health check failed")
            return False
        finally:
            db.close()

    @app.get("/health", response_model=HealthRead, tags=["Health"], summary="Health check")
    def health() -> HealthRead:
        """
        Confirm the engine is running and check Amanah worker configuration.

        - `status`: always `ok` when the server responds
        - `amanah_write_enabled`: whether Amanah can auto-execute legs
        """
        db_ok = _database_ok()
        status = "ok" if db_ok else "degraded"
        return HealthRead(
            status=status,
            version=__version__,
            amanah_write_enabled=settings.amanah_write_enabled,
            kenya_integration_mode=settings.kenya_integration_mode,
            mpesa_configured=settings.mpesa_configured,
            mno_safaricom_configured=settings.mno_safaricom_configured,
            airtel_money_configured=settings.airtel_money_configured,
            broker_configured=settings.broker_configured,
            shariah_audit_mirror=bool(settings.shariah_audit_service_url),
            auth_enabled=settings.auth_enabled,
            database_ok=db_ok,
            malaysia_commodity_desk=settings.malaysia_commodity_desk,
            bsas_live_configured=settings.bsas_live_configured,
            eiger_configured=settings.eiger_configured,
            manual_bridge_ready=settings.manual_bridge_path.exists(),
            sedania_mode=settings.sedania_mode,
            sedania_configured=settings.sedania_configured,
            deployment_mode=settings.normalized_mode,
            enabled_products=settings.products,
            brand_name=settings.brand_display,
            uptime_seconds=max(0, int(time.time() - PROCESS_STARTED_AT)),
            uptime_pct=100 if status == "ok" else 0,
        )

    @app.get("/metrics", include_in_schema=False, tags=["Production Ops"])
    def prometheus_metrics() -> PlainTextResponse:
        """Prometheus text exposition (public scrape endpoint)."""
        db = SessionLocal()
        try:
            data = collect_ops_metrics(db, settings)
        finally:
            db.close()
        return PlainTextResponse(content=render_prometheus(data), media_type="text/plain; version=0.0.4")

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{brand} Tawarruq Engine API v{__version__}",
            swagger_ui_parameters={
                "docExpansion": "list",
                "defaultModelsExpandDepth": 2,
                "displayRequestDuration": True,
                "filter": True,
                "tryItOutEnabled": True,
                "persistAuthorization": True,
            },
        )

    @app.get("/", include_in_schema=False)
    def root():
        return JSONResponse(
            {
                "name": f"{brand} Tawarruq Engine",
                "version": __version__,
                "docs": "/docs",
                "redoc": "/redoc",
                "openapi": "/openapi.json",
                "health": "/health",
                "api_prefix": settings.api_prefix,
                **settings.deployment_public(),
            }
        )

    app.include_router(router, prefix=settings.api_prefix)
    app.include_router(extended_router, prefix=settings.api_prefix)
    app.include_router(integrations_router, prefix=settings.api_prefix)
    app.include_router(ops_router, prefix=settings.api_prefix)
    app.include_router(controls_router, prefix=settings.api_prefix)
    app.include_router(customer_router, prefix=settings.api_prefix)
    if settings.product_enabled("sacco"):
        app.include_router(sacco_router, prefix=settings.api_prefix)
    if settings.product_enabled("sedania"):
        app.include_router(sedania_router, prefix=settings.api_prefix)
    if settings.product_enabled("kenya"):
        app.include_router(kenya_router, prefix=settings.api_prefix)
        app.include_router(callbacks_router, prefix=settings.api_prefix)
    if settings.product_enabled("malaysia"):
        app.include_router(manual_bridge_router, prefix=settings.api_prefix)
    if settings.product_enabled("mobile"):
        app.include_router(ops_mobile_router, prefix=settings.api_prefix)
        app.include_router(mobile_auth_router, prefix=settings.api_prefix)
    return app


app = create_app()
