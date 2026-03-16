from __future__ import annotations

# =====================================================
# IMPORTS
# =====================================================

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from prometheus_fastapi_instrumentator import Instrumentator
from scalar_fastapi import get_scalar_api_reference

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# -----------------------------------------------------
# ROUTERS
# -----------------------------------------------------

from app.api.v1 import api_router_v1
from app.api.v2 import api_router_v2
from app.api.version import router as version_router

from app.api.v1.endpoints.operaciones import router as operaciones_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.usuarios import router as usuarios_router

from app.routers.categorias import router as categorias_router
from app.oauth.router import router as oauth_router

# -----------------------------------------------------
# CORE
# -----------------------------------------------------

from app.core.config import limiter, settings
from app.core.exceptions import ItemNoEncontradoError, StockInsuficienteError
from app.core.logger import setup_logging

# -----------------------------------------------------
# DATABASE
# -----------------------------------------------------

from app.database.database import Base, SessionLocal, engine

# -----------------------------------------------------
# DISCOVERY
# -----------------------------------------------------

from app.discovery.consul_client import deregister_service, register_service

# -----------------------------------------------------
# MIDDLEWARES
# -----------------------------------------------------

from app.middlewares.audit_context import AuditContextMiddleware
from app.middlewares.content_type_validation import ContentTypeValidationMiddleware
from app.middlewares.dynamic_cors import DynamicCORSMiddleware
from app.middlewares.request_id import RequestIdMiddleware
from app.middlewares.request_logging import RequestLoggingMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware
from app.middlewares.sql_injection_warning import SQLInjectionWarningMiddleware
from app.middlewares.threat_detection import ThreatDetectionMiddleware
from app.middlewares.security_anomaly import SecurityAnomalyMiddleware

# -----------------------------------------------------
# SERVICES
# -----------------------------------------------------

from app.services.metrics_service import sync_active_items_gauge


# =====================================================
# OPENAPI TAGS
# =====================================================

OPENAPI_TAGS = [
    {"name": "Items", "description": "Operaciones sobre items"},
    {"name": "Auth", "description": "Autenticación JWT"},
    {"name": "Health", "description": "Healthchecks del sistema"},
    {"name": "Usuarios", "description": "Gestión de usuarios y derechos ARCO"},
]


# =====================================================
# APP FACTORY
# =====================================================

def create_app() -> FastAPI:
    """
    Crea y configura la instancia principal de FastAPI.
    """

    setup_logging()

    docs_url = "/docs"
    redoc_url = "/redoc"
    openapi_url = "/openapi.json"

    if settings.APP_ENV == "production":
        docs_url = None
        redoc_url = None
        openapi_url = None

    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="API JMV",
        openapi_tags=OPENAPI_TAGS,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    app.state.consul_service_id = None

    # =================================================
    # RATE LIMIT
    # =================================================

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # =================================================
    # MIDDLEWARES
    # =================================================

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(AuditContextMiddleware)
    app.add_middleware(ThreatDetectionMiddleware)
    app.add_middleware(ContentTypeValidationMiddleware)
    app.add_middleware(DynamicCORSMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SQLInjectionWarningMiddleware)
    app.add_middleware(SecurityAnomalyMiddleware)

    # =================================================
    # DB INIT
    # =================================================

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        sync_active_items_gauge(db)
    finally:
        db.close()

    # =================================================
    # CONSUL DISCOVERY
    # =================================================

    @app.on_event("startup")
    async def register_consul():
        if not settings.CONSUL_ENABLED:
            return

        service_id = register_service(
            name=settings.SERVICE_NAME,
            port=settings.SERVICE_PORT,
            tags=settings.service_tags_list,
        )

        app.state.consul_service_id = service_id

    @app.on_event("shutdown")
    async def deregister_consul():

        if not settings.CONSUL_ENABLED:
            return

        service_id = getattr(app.state, "consul_service_id", None)

        if service_id:
            deregister_service(service_id)

    # =================================================
    # EXCEPTION HANDLERS
    # =================================================

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):

        errores = []

        for err in exc.errors():
            loc = " -> ".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "Error de validación")
            errores.append(f"{loc}: {msg}")

        request_id = getattr(request.state, "request_id", None)

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Error de validación",
                "data": {"errors": errores},
                "metadata": {"request_id": request_id} if request_id else {},
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):

        request_id = getattr(request.state, "request_id", None)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": str(exc.detail),
                "data": None,
                "metadata": {"request_id": request_id} if request_id else {},
            },
        )

    @app.exception_handler(ItemNoEncontradoError)
    async def item_no_encontrado_handler(request: Request, exc: ItemNoEncontradoError):

        request_id = getattr(request.state, "request_id", None)

        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": f"Item no encontrado {exc.item_id}",
                "data": None,
                "metadata": {"request_id": request_id} if request_id else {},
            },
        )

    @app.exception_handler(StockInsuficienteError)
    async def stock_handler(request: Request, exc: StockInsuficienteError):

        request_id = getattr(request.state, "request_id", None)

        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "Stock insuficiente",
                "data": None,
                "metadata": {"request_id": request_id} if request_id else {},
            },
        )

    # =================================================
    # DOCS ALTERNATIVAS
    # =================================================

    @app.get("/scalar", include_in_schema=False)
    async def scalar_docs() -> HTMLResponse:

        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=f"{settings.APP_NAME} - Scalar",
        )

    # =================================================
    # SECURITY.TXT
    # =================================================

    @app.get("/.well-known/security.txt", include_in_schema=False)
    async def security_txt():

        content = """
Contact: mailto:security@empresa.com
Expires: 2030-12-31T23:59:59.000Z
Preferred-Languages: es,en
Policy: https://empresa.com/security-policy
"""

        return PlainTextResponse(content.strip())

    # =================================================
    # ROUTERS
    # =================================================

    app.include_router(health_router)

    app.include_router(categorias_router)

    app.include_router(version_router, prefix="/api")

    app.include_router(api_router_v1, prefix="/api/v1")

    app.include_router(api_router_v2, prefix="/api/v2")

    app.include_router(operaciones_router, prefix="/api/v1")

    # -------------------------------------------------
    # USUARIOS (GDPR / LFPDPPP)
    # -------------------------------------------------

    app.include_router(
        usuarios_router,
        prefix="/api/v1/usuarios",
        tags=["Usuarios"],
    )

    app.include_router(oauth_router)

    # =================================================
    # PROMETHEUS
    # =================================================

    Instrumentator().instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
    )

    return app


# =====================================================
# APP INSTANCE
# =====================================================

app = create_app()