from __future__ import annotations

import asyncio
import logging
import sentry_sdk
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# ROUTERS
from app.api.v1 import api_router_v1
from app.api.v1.endpoints.debug import router as debug_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.operaciones import router as operaciones_router
from app.api.v1.endpoints.sagas import router as sagas_router
from app.api.v1.endpoints.usuarios import router as usuarios_router
from app.api.v1.endpoints.chaos import router as chaos_router
from app.api.v2 import api_router_v2
from app.api.version import router as version_router

# CORE
from app.core.config import limiter, settings
from app.core.exceptions import ItemNoEncontradoError, StockInsuficienteError
from app.core.logger import setup_logging

# SENTRY
from app.core.sentry import init_sentry

# DB
from app.database.database import Base, SessionLocal, engine

# DISCOVERY
from app.discovery.consul_client import deregister_service, register_service
from app.middleware.sentry_user import SentryUserMiddleware

# MIDDLEWARES
from app.middlewares.audit_context import AuditContextMiddleware
from app.middlewares.auto_profiler import AutoProfilerMiddleware
from app.middlewares.content_type_validation import ContentTypeValidationMiddleware
from app.middlewares.dynamic_cors import DynamicCORSMiddleware
from app.middlewares.elk_logging import ELKLoggingMiddleware
from app.middlewares.request_id import RequestIdMiddleware
from app.middlewares.request_logging import RequestLoggingMiddleware
#--from app.middlewares.security_anomaly import SecurityAnomalyMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware
from app.middlewares.sql_injection_warning import SQLInjectionWarningMiddleware
#--from app.middlewares.threat_detection import ThreatDetectionMiddleware
from app.middlewares.trace_id import TraceIdMiddleware
#--from app.middlewares.backpressure import BackpressureMiddleware
from app.middlewares.priority import PriorityMiddleware
from app.middlewares.chaos import ChaosMiddleware

from app.oauth.router import router as oauth_router
from app.routers.categorias import router as categorias_router

# ELASTICSEARCH
from app.search.elasticsearch_client import create_index

from app.storage.s3_client import create_bucket_if_not_exists

# SERVICES
from app.services.metrics_service import (
    sync_active_items_gauge,
    sync_active_users_gauge,
)

logger = logging.getLogger(__name__)

init_sentry()


# =====================================================
# LIFESPAN
# =====================================================
@asynccontextmanager
async def lifespan(app: FastAPI):

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("DB inicializada")
    except Exception as e:
        logger.warning(f"DB error: {e}")

    # 🔥 NUEVO: CREAR BUCKET
    try:
        create_bucket_if_not_exists()
        logger.info("S3 bucket OK")
    except Exception as e:
        logger.warning(f"S3 error: {e}")

    try:
        db = SessionLocal()
        sync_active_items_gauge(db)
        sync_active_users_gauge(db)
        db.close()
    except Exception as e:
        logger.warning(f"Metrics error: {e}")

    if getattr(settings, "ELASTIC_ENABLED", False):
        try:
            await asyncio.to_thread(create_index)
            logger.info("Elasticsearch OK")
        except Exception as e:
            logger.warning(f"Elasticsearch OFF: {e}")

    if getattr(settings, "CONSUL_ENABLED", False):
        service_id = register_service(
            name=settings.SERVICE_NAME,
            port=settings.SERVICE_PORT,
            tags=settings.service_tags_list,
        )
        app.state.consul_service_id = service_id

    yield

    if getattr(settings, "CONSUL_ENABLED", False):
        sid = getattr(app.state, "consul_service_id", None)
        if sid:
            deregister_service(sid)


# =====================================================
# APP
# =====================================================
def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )

    sentry_sdk.set_tag("release", settings.VERSION)

    app.state.limiter = limiter

    # ==============================
    # RATE LIMIT
    # ==============================
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": "Rate limit exceeded",
                "data": {},
                "metadata": {"errors": []},
            },
        )

    # ==============================
    # MIDDLEWARES (ORDEN CORRECTO)
    # ==============================

    #--IDENTIDAD Y TRACE (SIEMPRE PRIMERO)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(TraceIdMiddleware)

    #--SEGURIDAD BÁSICA
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(ContentTypeValidationMiddleware)

    #--CORS
    app.add_middleware(DynamicCORSMiddleware)

    #--RATE LIMIT (ANTES DE LOGGING)
    app.add_middleware(SlowAPIMiddleware)

    #--CONTEXTO
    app.add_middleware(AuditContextMiddleware)

    #--LOGGING (DESPUÉS DE TODO LO ANTERIOR)
    app.add_middleware(RequestLoggingMiddleware)

    #--SQL / VALIDACIONES
    app.add_middleware(SQLInjectionWarningMiddleware)

    #--OBSERVABILIDAD (PUEDEN FALLAR)
    app.add_middleware(ELKLoggingMiddleware)
    app.add_middleware(SentryUserMiddleware)

    #--PROFILER (OPCIONAL)
    app.add_middleware(AutoProfilerMiddleware)

    #--PRIORITY (AL FINAL)
    app.add_middleware(PriorityMiddleware)

    #--CHAOS SOLO EN NO TEST
    if not getattr(settings, "TESTING", False):
        app.add_middleware(ChaosMiddleware)


    # ==============================
    # EXCEPTIONS
    # ==============================
    def build_validation_response(exc: RequestValidationError):
        errors = []

        try:
            for e in exc.errors() or []:
                errors.append({
                    "loc": e.get("loc"),
                    "msg": str(e.get("msg")),
                    "type": e.get("type"),
                })
        except Exception:
            errors = []

        return {
            "success": False,
            "message": "Error de validación",
            "data": {
                "errors": errors  # 🔥 FIX CLAVE
            },
            "metadata": {},
        }

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content=build_validation_response(exc))

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": str(exc.detail),
                "data": {},
                "metadata": {"errors": []},
            },
        )

    @app.exception_handler(ItemNoEncontradoError)
    async def item_handler(request: Request, exc: ItemNoEncontradoError):
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": exc.message,
                "data": {"item_id": exc.item_id},
                "metadata": {"errors": []},
            },
        )

    @app.exception_handler(StockInsuficienteError)
    async def stock_handler(request: Request, exc: StockInsuficienteError):
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": exc.message,
                "data": {
                    "item_id": exc.item_id,
                    "stock_actual": exc.stock_actual,
                },
                "metadata": {"errors": []},
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):

        if isinstance(exc, RequestValidationError):
            return JSONResponse(
                status_code=422,
                content=build_validation_response(exc),
            )

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error",
                "data": {},
                "metadata": {"errors": []},
            },
        )

    # ==============================
    # ROUTERS
    # ==============================
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

    if not getattr(settings, "TESTING", False):
        app.include_router(chaos_router, prefix="/api/v1")

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    return app


app = create_app()