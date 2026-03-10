from __future__ import annotations

"""
Servicios auxiliares para sincronizar métricas de negocio.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.metrics import ACTIVE_ITEMS_GAUGE
from app.models.item import Item


def sync_active_items_gauge(db: Session) -> None:
    """
    Sincroniza el gauge con el total real de items activos
    (no eliminados lógicamente).
    """
    total = (
        db.query(func.count(Item.id))
        .filter(Item.eliminado.is_(False))
        .scalar()
    ) or 0

    ACTIVE_ITEMS_GAUGE.set(float(total))