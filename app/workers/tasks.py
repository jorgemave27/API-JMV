from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.categoria import Categoria  # noqa: F401
from app.models.item import Item
from app.models.reporte_stock import ReporteStock
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.enviar_notificacion")
def enviar_notificacion(item_id: int, email: str) -> dict:
    """
    Simula el envío de una notificación por email.
    """
    logger.info(
        "Iniciando envío de notificación para item_id=%s a email=%s",
        item_id,
        email,
    )
    time.sleep(2)
    logger.info(
        "Notificación enviada para item_id=%s a email=%s",
        item_id,
        email,
    )
    return {
        "item_id": item_id,
        "email": email,
        "status": "enviado",
    }


@celery_app.task(name="app.workers.tasks.generar_reporte_stock_bajo")
def generar_reporte_stock_bajo() -> dict:
    """
    Genera un reporte de items con stock bajo (< 5) y lo guarda en BD.
    """
    db: Session = SessionLocal()
    try:
        stmt = (
            select(Item)
            .where(Item.eliminado == False)  # noqa: E712
            .where(Item.stock < 5)
            .order_by(Item.stock.asc(), Item.id.asc())
        )

        items = db.execute(stmt).scalars().all()

        contenido = [
            {
                "id": item.id,
                "name": item.name,
                "sku": item.sku,
                "stock": item.stock,
                "price": float(item.price),
                "categoria_id": item.categoria_id,
            }
            for item in items
        ]

        reporte = ReporteStock(
            tipo="stock_bajo",
            total_items=len(contenido),
            umbral=5,
            contenido=contenido,
        )

        db.add(reporte)
        db.commit()
        db.refresh(reporte)

        logger.info(
            "Reporte de stock bajo generado. reporte_id=%s total_items=%s",
            reporte.id,
            reporte.total_items,
        )

        return {
            "reporte_id": reporte.id,
            "total_items": reporte.total_items,
            "status": "generado",
        }
    finally:
        db.close()