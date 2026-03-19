from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String

from app.database.database import Base


class AuditoriaItem(Base):
    """
    Tabla de auditoría para cambios en items.

    Registra:
    - qué item cambió
    - qué acción ocurrió (CREATE / UPDATE / DELETE)
    - estado anterior
    - estado nuevo
    - usuario responsable
    - timestamp
    - IP del cliente

    Compatible con SQLite y PostgreSQL.
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
    # Acción realizada
    # -------------------------------------------------------------
    accion = Column(String(20), nullable=False, index=True)

    # -------------------------------------------------------------
    # Snapshot anterior y nuevo del item
    # -------------------------------------------------------------
    datos_anteriores = Column(JSON, nullable=True)
    datos_nuevos = Column(JSON, nullable=True)

    # -------------------------------------------------------------
    # Usuario responsable
    # -------------------------------------------------------------
    usuario_id = Column(Integer, nullable=True, index=True)

    # -------------------------------------------------------------
    # Metadata de trazabilidad
    # -------------------------------------------------------------
    timestamp = Column(
        DateTime,
        default=datetime.utcnow,  # ✅ compatible SQLite/Postgres
        nullable=False,
        index=True,
    )

    ip_cliente = Column(String(64), nullable=True)
