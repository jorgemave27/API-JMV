"""
MODELO: NOTIFICACIONES ENVIADAS

Guarda histórico de:
- qué se envió
- por qué canal
- si falló
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime

from app.database.database import Base


class NotificacionEnviada(Base):
    __tablename__ = "notificaciones_enviadas"

    id = Column(Integer, primary_key=True, index=True)

    # destinatario (email o teléfono)
    destinatario = Column(String, nullable=False)

    # canal usado (email / sms)
    canal = Column(String, nullable=False)

    # tipo de notificación (bienvenida, stock_bajo, etc)
    tipo = Column(String, nullable=False)

    # estado: enviado / error
    estado = Column(String, nullable=False)

    # número de intentos
    intentos = Column(Integer, default=1)

    # error si ocurrió
    error_mensaje = Column(Text, nullable=True)

    # timestamp
    enviado_en = Column(DateTime, default=datetime.utcnow)