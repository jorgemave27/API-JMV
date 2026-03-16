from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.database import Base


class ConsentimientoPrivacidad(Base):
    """
    Registro de aceptación del aviso de privacidad.

    Cumple con:
    - GDPR
    - LFPDPPP
    """

    __tablename__ = "consentimientos_privacidad"

    id = Column(Integer, primary_key=True, index=True)

    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False,
        index=True
    )

    version_aviso = Column(
        String(50),
        nullable=False,
        comment="Versión del aviso de privacidad aceptado"
    )

    ip_cliente = Column(
        String(45),
        nullable=False,
        comment="IP del cliente al aceptar el aviso"
    )

    fecha_aceptacion = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    usuario = relationship("Usuario")