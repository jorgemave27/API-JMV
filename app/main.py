from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import ItemNoEncontradoError, StockInsuficienteError
from app.core.logger import setup_logging
from app.database.database import Base, engine
from app.middlewares.request_id import RequestIdMiddleware
from app.middlewares.request_logging import RequestLoggingMiddleware
from app.routers.health import router as health_router
from app.routers.items import router as items_router


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="API JMV - FastAPI + SQLAlchemy + buenas prácticas",
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # Crea tablas (en producción usarías migraciones; para tareas iniciales sirve)
    Base.metadata.create_all(bind=engine)

    # ------------------------
    # Exception handlers
    # ------------------------

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

    # Routers
    app.include_router(health_router)
    app.include_router(items_router)

    return app


app = create_app()