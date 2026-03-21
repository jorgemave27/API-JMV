from __future__ import annotations

# =====================================================
# IMPORTS
# =====================================================
import asyncio
import logging
import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# -----------------------------------------------------
# ROUTERS
# -----------------------------------------------------
from app.api.v1 import api_router_v1
from app.api.v1.endpoints.debug import router as debug_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.operaciones import router as operaciones_router
from app.api.v1.endpoints.sagas import router as sagas_router
from app.api.v1.endpoints.usuarios import router as usuarios_router
from app.api.v2 import api_router_v2
from app.api.version import router as version_router

# -----------------------------------------------------
# CORE
# -----------------------------------------------------
from app.core.config import limiter, settings
from app.core.exceptions import ItemNoEncontradoError, StockInsuficienteError
from app.core.logger import setup_logging

# -----------------------------------------------------
# SENTRY
# -----------------------------------------------------
from app.core.sentry import init_sentry

# -----------------------------------------------------
# DATABASE
# -----------------------------------------------------
from app.database.database import Base, SessionLocal, engine

# -----------------------------------------------------
# MODELOS
# -----------------------------------------------------
from app.models.pedido import Pedido  # noqa
from app.models.saga_log import SagaLog  # noqa

# -----------------------------------------------------
# DISCOVERY
# -----------------------------------------------------
from app.discovery.consul_client import deregister_service, register_service
from app.middleware.sentry_user import SentryUserMiddleware

# -----------------------------------------------------
# MIDDLEWARES
# -----------------------------------------------------
from app.middlewares.audit_context import AuditContextMiddleware
from app.middlewares.auto_profiler import AutoProfilerMiddleware
from app.middlewares.content_type_validation import ContentTypeValidationMiddleware
from app.middlewares.dynamic_cors import DynamicCORSMiddleware
from app.middlewares.elk_logging import ELKLoggingMiddleware
from app.middlewares.request_id import RequestIdMiddleware
from app.middlewares.request_logging import RequestLoggingMiddleware
from app.middlewares.security_anomaly import SecurityAnomalyMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware
from app.middlewares.sql_injection_warning import SQLInjectionWarningMiddleware
from app.middlewares.threat_detection import ThreatDetectionMiddleware
from app.middlewares.trace_id import TraceIdMiddleware
from app.middlewares.backpressure import BackpressureMiddleware
from app.middlewares.priority import PriorityMiddleware

from app.oauth.router import router as oauth_router
from app.routers.categorias import router as categorias_router

# 🔥 ELASTICSEARCH
from app.search.elasticsearch_client import create_index

# -----------------------------------------------------
# SERVICES
# -----------------------------------------------------
from app.services.metrics_service import (
    sync_active_items_gauge,
    sync_active_users_gauge,
)

# =====================================================
# LOGGER
# =====================================================
logger = logging.getLogger(__name__)

# =====================================================
# INIT SENTRY
# =====================================================
init_sentry()

# =====================================================
# OPENAPI TAGS
# =====================================================
OPENAPI_TAGS = [
    {"name": "Items", "description": "Operaciones sobre items"},
    {"name": "Auth", "description": "Autenticación JWT"},
    {"name": "Health", "description": "Healthchecks del sistema"},
    {"name": "Usuarios", "description": "Gestión de usuarios"},
    {"name": "Sagas", "description": "Sagas distribuidas"},
]


# =====================================================
# APP FACTORY
# =====================================================
def create_app() -> FastAPI:
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
        version=settings.VERSION,
        description="API JMV",
        openapi_tags=OPENAPI_TAGS,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    sentry_sdk.set_tag("release", settings.VERSION)

    app.state.consul_service_id = None

    # =================================================
    # RATE LIMIT
    # =================================================
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # =================================================
    # MIDDLEWARES
    # =================================================
    app.add_middleware(PriorityMiddleware)
    app.add_middleware(BackpressureMiddleware)

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(AuditContextMiddleware)
    app.add_middleware(ThreatDetectionMiddleware)
    app.add_middleware(ContentTypeValidationMiddleware)
    app.add_middleware(DynamicCORSMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AutoProfilerMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SQLInjectionWarningMiddleware)
    app.add_middleware(SecurityAnomalyMiddleware)
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(ELKLoggingMiddleware)
    app.add_middleware(SentryUserMiddleware)

    # =================================================
    # STARTUP
    # =================================================
    @app.on_event("startup")
    async def startup_tasks():
        # 🔥 DB INIT
        try:
            await asyncio.to_thread(Base.metadata.create_all, bind=engine)
            logger.info("DB inicializada correctamente")
        except Exception as exc:
            logger.warning(f"Error inicializando DB: {exc}")

        # 🔥 MÉTRICAS (YA CON TABLAS)
        try:
            db = SessionLocal()
            try:
                sync_active_items_gauge(db)
                sync_active_users_gauge(db)
            finally:
                db.close()
        except Exception as exc:
            logger.warning(f"Error inicializando métricas: {exc}")

        # 🔥 ELASTICSEARCH
        try:
            await asyncio.to_thread(create_index)
            logger.info("Elasticsearch index verificado/creado")
        except Exception as exc:
            logger.warning(f"Error creando índice Elasticsearch: {exc}")

        # 🔥 CONSUL
        if settings.CONSUL_ENABLED:
            service_id = register_service(
                name=settings.SERVICE_NAME,
                port=settings.SERVICE_PORT,
                tags=settings.service_tags_list,
            )
            app.state.consul_service_id = service_id

    @app.on_event("shutdown")
    async def shutdown_tasks():
        if settings.CONSUL_ENABLED:
            service_id = getattr(app.state, "consul_service_id", None)
            if service_id:
                deregister_service(service_id)

    # =================================================
    # EXCEPTIONS
    # =================================================
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"success": False, "message": "Error de validación", "data": str(exc)},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": str(exc.detail)},
        )

    @app.exception_handler(ItemNoEncontradoError)
    async def item_handler(request: Request, exc: ItemNoEncontradoError):
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": exc.message},
        )

    @app.exception_handler(StockInsuficienteError)
    async def stock_handler(request: Request, exc: StockInsuficienteError):
        return JSONResponse(
            status_code=409,
            content={"success": False, "message": exc.message},
        )

    # =================================================
    # ROUTERS
    # =================================================
    app.include_router(health_router)
    app.include_router(categorias_router)
    app.include_router(version_router, prefix="/api")
    app.include_router(api_router_v1, prefix="/api/v1")
    app.include_router(api_router_v2, prefix="/api/v2")
    app.include_router(operaciones_router, prefix="/api/v1")
    app.include_router(sagas_router, prefix="/api/v1")
    app.include_router(usuarios_router, prefix="/api/v1/usuarios")
    app.include_router(oauth_router)
    app.include_router(debug_router, prefix="/debug")

    # =================================================
    # METRICS
    # =================================================
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    return app


# =====================================================
# APP INSTANCE
# =====================================================
app = create_app()