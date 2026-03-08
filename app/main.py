from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import api_router_v1
from app.api.v2 import api_router_v2
from app.api.version import router as version_router
from app.core.config import limiter, settings
from app.core.exceptions import ItemNoEncontradoError, StockInsuficienteError
from app.core.logger import setup_logging
from app.database.database import Base, engine
from app.middlewares.dynamic_cors import DynamicCORSMiddleware
from app.middlewares.request_id import RequestIdMiddleware
from app.middlewares.request_logging import RequestLoggingMiddleware
from app.middlewares.security_headers import SecurityHeadersMiddleware
from app.models.categoria import Categoria
from app.models.configuracion_cors import ConfiguracionCors
from app.models.item import Item
from app.routers.categorias import router as categorias_router
from app.routers.health import router as health_router


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
    """
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="API JMV - FastAPI + SQLAlchemy + buenas prácticas",
    )

    # ------------------------
    # Rate limiting
    # ------------------------
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ------------------------
    # Middlewares globales
    # ------------------------
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(DynamicCORSMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # ------------------------
    # Base de datos
    # ------------------------
    # Crea tablas automáticamente en entorno local/desarrollo.
    # En un entorno productivo esto normalmente se manejaría con migraciones.
    #
    # Importar los modelos asegura que SQLAlchemy los registre
    # correctamente en Base.metadata antes de ejecutar create_all().
    Base.metadata.create_all(bind=engine)

    # ------------------------
    # Exception handlers
    # ------------------------

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

    # ------------------------
    # Routers
    # ------------------------

    # Healthcheck / utilitarios existentes
    app.include_router(health_router)

    # CRUD de categorías
    app.include_router(categorias_router)

    # Endpoint informativo de versión de API
    # Ejemplo: GET /api/version
    app.include_router(version_router, prefix="/api")

    # API versionada v1
    # Ejemplo: /api/v1/items
    app.include_router(api_router_v1, prefix="/api/v1")

    # API versionada v2
    # Ejemplo: /api/v2/items
    app.include_router(api_router_v2, prefix="/api/v2")

    return app


app = create_app()