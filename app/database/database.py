from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
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


def _build_async_database_url(database_url: str) -> str:
    """
    Convierte la DATABASE_URL sync a una URL async compatible con SQLAlchemy.

    Ejemplos:
    - sqlite:///./database.db         -> sqlite+aiosqlite:///./database.db
    - postgresql://user:pass@host/db  -> postgresql+asyncpg://user:pass@host/db
    """
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace(
            "postgresql+psycopg2://",
            "postgresql+asyncpg://",
            1,
        )

    return database_url


# ==========================================================
# Configuración SYNC (se conserva para no romper la API actual)
# ==========================================================
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
    Dependency sync de FastAPI para obtener una sesión de base de datos.

    Abre una sesión al iniciar el request y la cierra al finalizar,
    incluso si ocurre una excepción.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================================
# Configuración ASYNC (nueva para endpoints async)
# ==========================================================
async_database_url = _build_async_database_url(database_url)
is_async_sqlite = async_database_url.startswith("sqlite+aiosqlite")

async_engine_kwargs: dict[str, Any] = {
    "pool_pre_ping": True,
}

if is_async_sqlite:
    # Para SQLite async con aiosqlite
    async_engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Para PostgreSQL async con asyncpg
    async_engine_kwargs["pool_size"] = 10
    async_engine_kwargs["max_overflow"] = 20


async_engine = create_async_engine(
    async_database_url,
    **async_engine_kwargs,
)


AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db_async() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency async de FastAPI para obtener una AsyncSession.

    Se usa solo en endpoints async.
    """
    async with AsyncSessionLocal() as db:
        yield db