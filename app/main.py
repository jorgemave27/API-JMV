from __future__ import annotations

from fastapi import FastAPI

from app.core.config import settings
from app.database.database import Base, engine
from app.routers.health import router as health_router
from app.routers.items import router as items_router
from app.middlewares.request_id import RequestIdMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="API JMV - FastAPI + SQLAlchemy + buenas prácticas",
    )

    # Middleware para generar request_id por request
    app.add_middleware(RequestIdMiddleware)

    # Crea tablas (en producción usarías migraciones; para tareas iniciales sirve)
    Base.metadata.create_all(bind=engine)

    # Routers
    app.include_router(health_router)
    app.include_router(items_router)

    return app


app = create_app()