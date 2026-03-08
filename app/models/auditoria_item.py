from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.database.database import Base


class AuditoriaItem(Base):
    """
    Tabla de auditoría para cambios en items.

    Registra:
    - qué item cambió
    - qué acción ocurrió
    - estado anterior
    - estado nuevo
    - usuario responsable
    - timestamp
    - IP del cliente

    Esta tabla permite trazabilidad completa y reconstrucción histórica.
    """

    __tablename__ = "auditoria_items"

    # -------------------------------------------------------------
    # Identificación del registro de auditoría
    # -------------------------------------------------------------
    id = Column(Integer, primary_key=True, index=True)

    # -------------------------------------------------------------
    # Referencia lógica al item afectado
    # -------------------------------------------------------------
    item_id = Column(Integer, nullable=False, index=True)

    # -------------------------------------------------------------
    # Acción realizada:
    # CREATE / UPDATE / DELETE
    # -------------------------------------------------------------
    accion = Column(String(20), nullable=False, index=True)

    # -------------------------------------------------------------
    # Snapshot anterior y nuevo del item
    # -------------------------------------------------------------
    datos_anteriores = Column(JSON, nullable=True)
    datos_nuevos = Column(JSON, nullable=True)

    # -------------------------------------------------------------
    # Usuario responsable del cambio
    # -------------------------------------------------------------
    usuario_id = Column(Integer, nullable=True, index=True)

    # -------------------------------------------------------------
    # Metadata de trazabilidad
    # -------------------------------------------------------------
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    ip_cliente = Column(String(64), nullable=True)