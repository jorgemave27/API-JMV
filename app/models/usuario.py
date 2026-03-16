from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database.database import Base
from app.database.types.encrypted_string import EncryptedString


class Usuario(Base):
    """
    Modelo de usuario para autenticación JWT y control de acceso.

    Seguridad aplicada:
    - Nunca guarda contraseñas en texto plano
    - Usa hashed_password
    - Permite bloqueo temporal por fuerza bruta
    - Permite reset seguro con token de un solo uso
    - Campos sensibles cifrados a nivel de base de datos
    - Soporte para cumplimiento ARCO / GDPR / LFPDPPP
    """

    __tablename__ = "usuarios"

    # -------------------------------------------------------------
    # Identificación
    # -------------------------------------------------------------
    id = Column(Integer, primary_key=True, index=True)

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    # -------------------------------------------------------------
    # Datos personales
    # -------------------------------------------------------------
    nombre = Column(
        String(255),
        nullable=True,
        comment="Nombre del usuario"
    )

    # -------------------------------------------------------------
    # Datos sensibles cifrados
    # -------------------------------------------------------------
    # RFC almacenado cifrado usando AES-256-GCM.
    # Cuando SQLAlchemy guarda el valor → se cifra automáticamente
    # Cuando SQLAlchemy lee el valor → se descifra automáticamente
    # En la base de datos el valor se verá como texto cifrado.
    rfc = Column(
        EncryptedString(255),
        nullable=True,
        index=True,
        comment="RFC cifrado AES-256-GCM"
    )

    # -------------------------------------------------------------
    # Contraseña segura
    # -------------------------------------------------------------
    # IMPORTANTE:
    # Aquí solo se guarda el hash de la contraseña, nunca la contraseña
    # en texto plano.
    hashed_password = Column(
        String(255),
        nullable=False
    )

    # -------------------------------------------------------------
    # Estado del usuario
    # -------------------------------------------------------------
    activo = Column(
        Boolean,
        nullable=False,
        default=True
    )

    # Roles válidos: admin, editor, lector
    rol = Column(
        String(50),
        nullable=False,
        default="lector"
    )

    # -------------------------------------------------------------
    # Protección contra fuerza bruta
    # -------------------------------------------------------------
    failed_login_attempts = Column(
        Integer,
        nullable=False,
        default=0
    )

    blocked_until = Column(
        DateTime,
        nullable=True
    )

    # -------------------------------------------------------------
    # Reset seguro de contraseña
    # -------------------------------------------------------------
    reset_token_hash = Column(
        String(255),
        nullable=True
    )

    reset_token_expires_at = Column(
        DateTime,
        nullable=True
    )

    reset_token_used_at = Column(
        DateTime,
        nullable=True
    )

    # -------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Se usará después para retención automática de datos
    # y reportes de actividad de datos personales.
    ultimo_acceso_at = Column(
        DateTime,
        nullable=True
    )