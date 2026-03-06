from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """
    Clase base para todos los modelos ORM del proyecto.

    Todos los modelos SQLAlchemy deben heredar de esta clase para compartir
    la misma metadata. Alembic usa esta metadata para detectar cambios
    en el esquema de la base de datos.
    """
    pass


database_url = settings.DATABASE_URL
is_sqlite = database_url.startswith("sqlite")

engine_kwargs: dict[str, Any] = {
    "future": True,
    "pool_pre_ping": True,
}

if is_sqlite:
    # SQLite requiere check_same_thread=False cuando se usa con FastAPI.
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Pool de conexiones recomendado para PostgreSQL en producción.
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20


engine = create_engine(
    database_url,
    **engine_kwargs,
)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency de FastAPI para obtener una sesión de base de datos.

    Abre una sesión al iniciar el request y la cierra al finalizar,
    incluso si ocurre una excepción.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()