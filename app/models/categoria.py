from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database.database import Base


class Categoria(Base):
    """
    Modelo de categorías para relacionar items con una categoría opcional.

    Campos:
    - id: identificador único
    - nombre: nombre único de la categoría
    - descripcion: descripción opcional
    - creado_en: fecha de creación
    """

    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False, index=True)
    descripcion = Column(String(255), nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relación inversa:
    # una categoría puede tener muchos items
    items = relationship("Item", back_populates="categoria")
