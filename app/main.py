from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from scalar_fastapi import get_scalar_api_reference
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import api_router_v1
from app.api.v1.endpoints.health import router as health_router
from app.api.v2 import api_router_v2
from app.api.version import router as version_router
from app.core.config import limiter, settings
from app.core.exceptions import ItemNoEncontradoError, StockInsuficienteError
from app.core.logger import setup_logging
from app.database.database import Base, SessionLocal, engine
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


# =========================================================
# Metadata de tags para OpenAPI / Swagger / ReDoc / Scalar
# =========================================================
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
        "name": "Reportes",
        "description": (
            "Endpoints de reportes operativos y procesos asociados "
            "a stock y tareas de background."
        ),
    },
]


def create_app() -> FastAPI:
    """
    Factory principal de la aplicación FastAPI.

    Responsabilidades:
    - Inicializar logging
    - Crear la app
    - Registrar middlewares
    - Crear tablas en desarrollo
    - Registrar exception handlers
    - Incluir routers versionados y utilitarios
    - Exponer documentación enriquecida
    """
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
        docs_url="/docs",          # Swagger UI
        redoc_url="/redoc",        # ReDoc
        openapi_url="/openapi.json",
    )

    # -------------------------------------------------------------
    # Rate limiting
    # -------------------------------------------------------------
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # -------------------------------------------------------------
    # Middlewares globales
    # -------------------------------------------------------------
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(AuditContextMiddleware)  # Contexto para auditoría
    app.add_middleware(ThreatDetectionMiddleware)  # Detección de amenazas
    app.add_middleware(ContentTypeValidationMiddleware)  # Validación de Content-Type
    app.add_middleware(DynamicCORSMiddleware)  # CORS dinámico basado en DB
    app.add_middleware(SecurityHeadersMiddleware)  # Encabezados de seguridad
    app.add_middleware(RequestLoggingMiddleware)  # Logging de requests/responses
    app.add_middleware(RequestIdMiddleware)  # request_id para trazabilidad
    app.add_middleware(SQLInjectionWarningMiddleware)  # Detección de patrones SQLi

    # -------------------------------------------------------------
    # Base de datos
    # -------------------------------------------------------------
    # En desarrollo/local crea tablas a partir de metadata.
    # En producción el control real lo llevan Alembic + migraciones.
    Base.metadata.create_all(bind=engine)

    # -------------------------------------------------------------
    # Inicialización de métricas de negocio
    # -------------------------------------------------------------
    db = SessionLocal()
    try:
        sync_active_items_gauge(db)
    finally:
        db.close()

    # -------------------------------------------------------------
    # Exception handlers
    # -------------------------------------------------------------
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        Maneja errores de validación de Pydantic/FastAPI
        devolviendo una respuesta estandarizada.
        """
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
        """
        Maneja HTTPException genéricas con formato estandarizado.
        """
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
        """
        Maneja la excepción personalizada cuando un item no existe.
        """
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
        """
        Maneja la excepción personalizada para conflictos de stock.
        """
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

    # -------------------------------------------------------------
    # Router adicional para Scalar
    # -------------------------------------------------------------
    @app.get("/scalar", include_in_schema=False)
    async def scalar_docs() -> HTMLResponse:
        """
        Documentación moderna con Scalar.
        """
        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=f"{settings.APP_NAME} - Scalar",
        )

    # -------------------------------------------------------------
    # Routers
    # -------------------------------------------------------------
    # Health en raíz para compatibilidad con tests viejos: /health
    app.include_router(health_router)

    # Resto de routers
    app.include_router(categorias_router)
    app.include_router(version_router, prefix="/api")
    app.include_router(api_router_v1, prefix="/api/v1")
    app.include_router(api_router_v2, prefix="/api/v2")

    # -------------------------------------------------------------
    # Prometheus metrics
    # Expone /metrics automáticamente
    # -------------------------------------------------------------
    Instrumentator().instrument(app).expose(
        app,
        endpoint="/metrics",
        include_in_schema=False,
    )

    return app


app = create_app()