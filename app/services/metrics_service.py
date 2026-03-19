from __future__ import annotations

"""
Servicios auxiliares para sincronizar métricas de negocio.
"""

import time
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.metrics import (
    ACTIVE_ITEMS_GAUGE,
    ACTIVE_USERS_GAUGE,
    DB_QUERY_DURATION_SECONDS,
)
from app.models.item import Item
from app.models.usuario import Usuario


def sync_active_items_gauge(db: Session) -> None:
    """
    Sincroniza el gauge con el total real de items activos
    (no eliminados lógicamente).
    """
    total = (db.query(func.count(Item.id)).filter(Item.eliminado.is_(False)).scalar()) or 0

    ACTIVE_ITEMS_GAUGE.set(float(total))


def sync_active_users_gauge(db: Session) -> None:
    """
    Sincroniza el gauge con el total real de usuarios activos.
    """
    total = (db.query(func.count(Usuario.id)).filter(Usuario.activo.is_(True)).scalar()) or 0

    ACTIVE_USERS_GAUGE.set(float(total))


@contextmanager
def measure_db_query(operation: str, table: str):
    """
    Context manager síncrono para medir latencia de queries SQLAlchemy sync.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        DB_QUERY_DURATION_SECONDS.labels(
            operation=operation,
            table=table,
        ).observe(elapsed)


@asynccontextmanager
async def measure_db_query_async(operation: str, table: str):
    """
    Context manager asíncrono para medir latencia de queries SQLAlchemy async.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        DB_QUERY_DURATION_SECONDS.labels(
            operation=operation,
            table=table,
        ).observe(elapsed)
