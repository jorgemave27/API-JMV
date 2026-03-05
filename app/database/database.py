from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Configuración de conexión
# SQLite necesita check_same_thread=False para desarrollo local
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


# Engine principal de SQLAlchemy
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    future=True,
)


# Fábrica de sesiones
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


def get_db():
    """
    Dependency de FastAPI:
    abre una sesión de base de datos y la cierra al finalizar el request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()