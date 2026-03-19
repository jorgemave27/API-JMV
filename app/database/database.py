from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


# ==========================================================
# BASE
# ==========================================================
class Base(DeclarativeBase):
    pass


# ==========================================================
# URL HELPERS
# ==========================================================
def _build_async_database_url(database_url: str) -> str:
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
# MAIN DB (WRITE - PGBOUNCER)
# ==========================================================
database_url = settings.DATABASE_URL
async_database_url = _build_async_database_url(database_url)

engine = create_engine(
    database_url,
    pool_size=50,          # 🔥 aumentado para PgBouncer
    max_overflow=100,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================================
# ASYNC MAIN
# ==========================================================
async_engine = create_async_engine(
    async_database_url,
    pool_size=50,
    max_overflow=100,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db_async() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        yield db


# ==========================================================
# READ REPLICA
# ==========================================================
if settings.DATABASE_READ_URL:
    read_engine = create_engine(
        settings.DATABASE_READ_URL,
        pool_size=50,
        max_overflow=100,
        pool_pre_ping=True,
    )

    ReadSessionLocal = sessionmaker(bind=read_engine)

    def get_read_db():
        db = ReadSessionLocal()
        try:
            yield db
        finally:
            db.close()
else:
    get_read_db = get_db


# ==========================================================
# SHARDING
# ==========================================================
if settings.DATABASE_SHARD_1 and settings.DATABASE_SHARD_2:
    shard1_engine = create_engine(settings.DATABASE_SHARD_1)
    shard2_engine = create_engine(settings.DATABASE_SHARD_2)

    Shard1Session = sessionmaker(bind=shard1_engine)
    Shard2Session = sessionmaker(bind=shard2_engine)
else:
    Shard1Session = SessionLocal
    Shard2Session = SessionLocal


class ShardRouter:
    """
    Router simple por rango de ID
    """

    @staticmethod
    def get_session(item_id: int):
        if item_id <= 500000:
            return Shard1Session()
        return Shard2Session()