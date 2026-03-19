"""
Endpoint admin para consultar eventos de seguridad.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.security_event import SecurityEvent

router = APIRouter(
    prefix="/admin/security",
    tags=["Admin Security"],
)


@router.get("/eventos")
def obtener_eventos_security(db: Session = Depends(get_db)):
    """
    Retorna los últimos eventos de seguridad detectados.
    """

    eventos = db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).limit(100).all()

    data = [
        {
            "id": e.id,
            "ip": e.ip,
            "tipo_evento": e.tipo_evento,
            "detalles": e.detalles,
            "accion_tomada": e.accion_tomada,
            "pais": e.pais,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in eventos
    ]

    return {
        "success": True,
        "total": len(data),
        "data": data,
    }
