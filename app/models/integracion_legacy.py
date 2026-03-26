from __future__ import annotations

"""
MODELO: IntegracionLegacy

Tabla que registra el procesamiento de archivos provenientes
de sistemas legacy (EDI vía SFTP).

Se utiliza para:
- Auditoría
- Idempotencia (evitar reprocesar archivos)
- Métricas de integración
"""

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from app.database.database import Base


class IntegracionLegacy(Base):
    __tablename__ = "integraciones_legacy"

    # ID único
    id = Column(Integer, primary_key=True, index=True)

    # Nombre del archivo procesado
    nombre_archivo = Column(String, nullable=False)

    # Hash SHA256 del archivo (clave de idempotencia)
    hash_archivo = Column(String, unique=True, index=True)

    # Cantidad de items procesados correctamente
    items_procesados = Column(Integer, default=0)

    # Cantidad de items que fallaron
    items_fallidos = Column(Integer, default=0)

    # Tiempo total de procesamiento en segundos
    tiempo_procesamiento = Column(Integer)

    # Timestamp de creación
    creado_en = Column(DateTime, default=datetime.utcnow)