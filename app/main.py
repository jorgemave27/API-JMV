from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from scalar_fastapi import get_scalar_api_reference
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.endpoints.operaciones import router as operaciones_router
from app.models.item_lectura import ItemLectura
from app.api.v1 import api_router_v1
from app.api.v1.endpoints.health import router as health_router
from app.api.v2 import api_router_v2
from app.api.version import router as version_router
from app.core.config import limiter, settings
from app.core.exceptions import ItemNoEncontradoError, StockInsuficienteError
from app.core.logger import setup_logging
from app.database.database import Base, SessionLocal, engine
from app.discovery.consul_client import deregister_service, register_service
from app.middlewares.audit_context import AuditContextMiddleware
from app.middlewares.content_type_validation import ContentTypeValidationMiddleware
from app.middlewares.dynamic_cors import DynamicCORSMiddleware
from app.middlewares.request_id import RequestIdMiddleware
from app.middlewares.request_logging import RequestLoggingMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware
from app.middlewares.sql_injection_warning import SQLInjectionWarningMiddleware
from app.middlewares.threat_detection import ThreatDetectionMiddleware
from app.models.auditoria_item import AuditoriaItem
from app.models.categoria import Categoria
from app.models.configuracion_cors import ConfiguracionCors
from app.models.item import Item
from app.routers.categorias import router as categorias_router
from app.services.metrics_service import sync_active_items_gauge


OPENAPI_TAGS = [
    {
        "name": "Items",
        "description": (
            "Operaciones sobre items de inventario: creación, consulta, "
            "filtros, paginación, soft delete, restauración, auditoría "
            "y movimientos de stock."
        ),
        "externalDocs": {
            "description": "Guía funcional de items",
            "url": "https://example.com/docs/items",
        },
    },
    {
        "name": "Auth",
        "description": (
            "Autenticación y autorización con JWT, refresh token "
            "y control de acceso por roles."
        ),
        "externalDocs": {
            "description": "Guía de autenticación",
            "url": "https://example.com/docs/auth",
        },
    },
    {
        "name": "CORS Admin",
        "description": (
            "Administración dinámica de orígenes permitidos para CORS "
            "desde base de datos."
        ),
    },
    {
        "name": "Health",
        "description": (
            "Healthchecks, disponibilidad del servicio y endpoints "
            "de diagnóstico."
        ),
    },
    {
        "name": "Usuarios",
        "description": (
            "Gestión de usuarios, roles y operaciones relacionadas "
            "con identidad del sistema."
        ),
    },
    {
        "name": "Admin Cache",
        "description": (
            "Administración de caché Redis, invalidación y diagnóstico "
            "de almacenamiento temporal."
        ),
    },
    {
        "name": "Admin Resilience",
        "description": (
            "Diagnóstico y pruebas de circuit breakers, resiliencia "
            "y fallback cacheado para servicios externos."
        ),
    },
    {
        "name": "Reportes",
        "description": (
            "Endpoints de reportes operativos y procesos asociados "
            "a stock y tareas de background."
        ),
    },
]


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description=(
            "API JMV - FastAPI + SQLAlchemy + buenas prácticas.\n\n"
            "Incluye autenticación JWT, RBAC, rate limiting, "
            "caché con Redis, auditoría, sanitización, detección "
            "de payloads sospechosos, CORS dinámico, métricas Prometheus "
            "y tareas background con Celery."
        ),
        contact={
            "name": "Equipo Backend",
            "email": "dev@empresa.com",
        },
        license_info={
            "name": "MIT",
        },
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.state.consul_service_id = None

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(AuditContextMiddleware)
    app.add_middleware(ThreatDetectionMiddleware)
    app.add_middleware(ContentTypeValidationMiddleware)
    app.add_middleware(DynamicCORSMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SQLInjectionWarningMiddleware)

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        sync_active_items_gauge(db)
    finally:
        db.close()

    @app.on_event("startup")
    async def on_startup_register_consul() -> None:
        if not settings.CONSUL_ENABLED:
            return

        service_id = register_service(
            name=settings.SERVICE_NAME,
            port=settings.SERVICE_PORT,
            tags=settings.service_tags_list,
        )
        app.state.consul_service_id = service_id

    @app.on_event("shutdown")
    async def on_shutdown_deregister_consul() -> None:
        if not settings.CONSUL_ENABLED:
            return

        service_id = getattr(app.state, "consul_service_id", None)
        if service_id:
            deregister_service(service_id)

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
                "message": "Error de validación en los datos enviados",
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
                "message": f"Item no encontrado con id={exc.item_id}",
                "data": {"item_id": exc.item_id},
                "metadata": {"request_id": request_id} if request_id else {},
            },
        )

    @app.exception_handler(StockInsuficienteError)
    async def stock_insuficiente_handler(request: Request, exc: StockInsuficienteError):
        request_id = getattr(request.state, "request_id", None)

        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": (
                    f"No se puede marcar disponible=True para el item {exc.item_id} "
                    f"porque su stock actual es {exc.stock_actual}"
                ),
                "data": {
                    "item_id": exc.item_id,
                    "stock_actual": exc.stock_actual,
                },
                "metadata": {"request_id": request_id} if request_id else {},
            },
        )

    @app.get("/scalar", include_in_schema=False)
    async def scalar_docs() -> HTMLResponse:
        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=f"{settings.APP_NAME} - Scalar",
        )

    app.include_router(health_router)
    app.include_router(categorias_router)
    app.include_router(version_router, prefix="/api")
    app.include_router(api_router_v1, prefix="/api/v1")
    app.include_router(api_router_v2, prefix="/api/v2")
    app.include_router(operaciones_router, prefix="/api/v1")

    Instrumentator().instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
    )

    return app


app = create_app()