from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database.database import Base


class Usuario(Base):
    """
    Modelo de usuario para autenticación JWT y control de acceso.
    """

    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)

    # Roles válidos: admin, editor, lector
    rol = Column(String(50), nullable=False, default="lector")

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )