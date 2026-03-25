from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.categoria import Categoria  # noqa
from app.models.item import Item
from app.models.reporte_stock import ReporteStock
from app.models.usuario import Usuario
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# =====================================================
# HELPERS GDPR
# =====================================================
def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _anon_email(email: str, user_id: int) -> str:
    digest = _sha256(email)
    return f"anon-{user_id}-{digest[:20]}@anon.local"


def _anon_name(name: str | None, user_id: int) -> str:
    base = name or f"user-{user_id}"
    digest = _sha256(base)
    return f"anon-{digest[:16]}"


def _anon_rfc(rfc: str | None, user_id: int) -> str | None:
    if not rfc:
        return None
    return _sha256(f"{user_id}:{rfc}")


# =====================================================
# 🔥 TASK NOTIFICACIONES (CORREGIDO)
# =====================================================
@celery_app.task(name="app.workers.tasks.enviar_notificacion", bind=True, max_retries=3)
def enviar_notificacion(self, payload: dict) -> dict:
    """
    Nueva versión:
    - Usa NotificationService
    - Maneja DB correctamente
    - Tiene retry con backoff
    """

    db: Session = SessionLocal()

    try:
        from app.notifications.notification_service import NotificationService

        service = NotificationService(db=db)

        service.send(
            destinatario=payload["destinatario"],
            tipo=payload["tipo"],
            canal=payload["canal"],
            context=payload["context"],
        )

        logger.info("Notificación enviada correctamente: %s", payload)

        return {
            "status": "enviado",
            "payload": payload,
        }

    except Exception as exc:
        logger.error("Error en notificación: %s", exc, exc_info=True)

        raise self.retry(
            exc=exc,
            countdown=2 ** self.request.retries
        )

    finally:
        db.close()


# =====================================================
# STOCK REPORT
# =====================================================
@celery_app.task(name="app.workers.tasks.generar_reporte_stock_bajo")
def generar_reporte_stock_bajo() -> dict:
    db: Session = SessionLocal()

    try:
        stmt = (
            select(Item)
            .where(Item.eliminado == False)  # noqa
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


# =====================================================
# GDPR DATA RETENTION
# =====================================================
@celery_app.task(name="app.workers.tasks.anonimizar_usuarios_inactivos")
def anonimizar_usuarios_inactivos() -> dict:
    db: Session = SessionLocal()

    try:
        limite = datetime.utcnow() - timedelta(days=365 * 3)

        stmt = select(Usuario).where(
            Usuario.ultimo_acceso_at != None,  # noqa
            Usuario.ultimo_acceso_at < limite,
            Usuario.activo == True,  # noqa
        )

        usuarios = db.execute(stmt).scalars().all()

        total = 0

        for user in usuarios:
            user.email = _anon_email(user.email, user.id)
            user.nombre = _anon_name(user.nombre, user.id)
            user.rfc = _anon_rfc(user.rfc, user.id)

            user.activo = False
            user.updated_at = datetime.utcnow()

            total += 1

        db.commit()

        logger.info(
            "GDPR retention ejecutado usuarios_anonimizados=%s",
            total,
        )

        return {
            "usuarios_anonimizados": total,
            "status": "ok",
        }

    finally:
        db.close()