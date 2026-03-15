"""
Modelo ORM para registrar eventos de seguridad detectados
por el sistema de anomalías.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class SecurityEvent(Base):
    """
    Tabla que almacena eventos de seguridad detectados.

    Permite auditar:
    - ataques de fuerza bruta
    - escaneo de endpoints
    - rate limit agresivo
    - IP bloqueadas
    """

    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    ip: Mapped[str] = mapped_column(String(45), index=True)

    tipo_evento: Mapped[str] = mapped_column(String(50))

    detalles: Mapped[str] = mapped_column(Text)

    accion_tomada: Mapped[str] = mapped_column(String(50))

    pais: Mapped[str | None] = mapped_column(String(10), nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
