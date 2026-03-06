from __future__ import annotations

from collections.abc import Generator

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


# Configuración especial para SQLite en desarrollo local.
# SQLite requiere check_same_thread=False cuando se usa con FastAPI.
connect_args: dict[str, bool] = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


# Engine principal de SQLAlchemy.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    future=True,
)


# Fábrica de sesiones de base de datos.
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