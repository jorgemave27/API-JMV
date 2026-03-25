"""
ENDPOINT ADMIN NOTIFICACIONES

Permite ver historial de notificaciones enviadas
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.notification import NotificacionEnviada

router = APIRouter()


@router.get("/admin/notificaciones")
def get_notificaciones(db: Session = Depends(get_db)):
    """
    Devuelve todas las notificaciones enviadas
    """
    data = db.query(NotificacionEnviada).all()

    return {
        "total": len(data),
        "data": data,
    }