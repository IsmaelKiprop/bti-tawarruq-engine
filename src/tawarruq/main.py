import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse, PlainTextResponse

from sqlalchemy import text

from tawarruq import __version__
from tawarruq.amanah.worker import AmanahWorker
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
from tawarruq.api.routes_sacco import router as sacco_router
from tawarruq.config import get_settings
from tawarruq.database import SessionLocal, init_db
from tawarruq.schemas import HealthRead
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.metrics_service import collect_ops_metrics, render_prometheus
from tawarruq.services.monitoring import RequestMetricsMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()

    from tawarruq.database import SessionLocal

    db = SessionLocal()
    try:
        get_or_create_default_institution(db)
        from tawarruq.services.seed_service import seed_kenya_defaults
        from tawarruq.services.ops_user_service import ensure_bootstrap_admin

        seed_kenya_defaults(db)
        admin = ensure_bootstrap_admin(db)
        db.commit()
        if admin:
            logger.warning(
                "Bootstrapped ops admin %s — change password on first login (must_change_password=true)",
                admin.email,
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
    app = FastAPI(
        title="Buruuj Tawarruq Engine API",
        description=API_DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
        contact={
            "name": "Buruuj Fintech",
            "url": "https://github.com/IsmaelKiprop/bti-tawarruq-engine",
        },
        license_info={"name": "Proprietary"},
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Inner middlewares first; CORS must be outermost so 401/403 still get ACAO headers.
    settings = get_settings()
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    portal_origin = (settings.portal_public_url or "").rstrip("/")
    if portal_origin and portal_origin not in cors_origins:
        cors_origins.append(portal_origin)

    app.add_middleware(ApiKeyMiddleware)
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
        return HealthRead(
            status="ok" if db_ok else "degraded",
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
            title=f"Buruuj Tawarruq Engine API v{__version__}",
            swagger_ui_parameters={
                "docExpansion": "list",
                "defaultModelsExpandDepth": 2,
                "displayRequestDuration": True,
                "filter": True,
                "tryItOutEnabled": True,
            },
        )

    @app.get("/", include_in_schema=False)
    def root():
        return JSONResponse(
            {
                "name": "Buruuj Tawarruq Engine",
                "version": __version__,
                "docs": "/docs",
                "redoc": "/redoc",
                "openapi": "/openapi.json",
                "health": "/health",
                "api_prefix": settings.api_prefix,
            }
        )

    app.include_router(router, prefix=settings.api_prefix)
    app.include_router(extended_router, prefix=settings.api_prefix)
    app.include_router(sacco_router, prefix=settings.api_prefix)
    app.include_router(kenya_router, prefix=settings.api_prefix)
    app.include_router(manual_bridge_router, prefix=settings.api_prefix)
    app.include_router(callbacks_router, prefix=settings.api_prefix)
    app.include_router(integrations_router, prefix=settings.api_prefix)
    app.include_router(ops_router, prefix=settings.api_prefix)
    app.include_router(ops_mobile_router, prefix=settings.api_prefix)
    app.include_router(mobile_auth_router, prefix=settings.api_prefix)
    app.include_router(customer_router, prefix=settings.api_prefix)
    return app


app = create_app()
