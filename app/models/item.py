from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Index
from sqlalchemy.orm import relationship

from app.database.database import Base


class Item(Base):
    """
    Modelo de Item dentro del sistema.

    Representa un producto o elemento gestionado por la API.

    Campos principales:
    - id: identificador único
    - name: nombre del item
    - description: descripción opcional
    - price: precio del item
    - sku: SKU legacy del sistema
    - codigo_sku: SKU con formato validado (AB-1234)
    - stock: cantidad disponible en inventario

    Soft delete:
    - eliminado: indica si el item fue eliminado lógicamente
    - eliminado_en: fecha en que se eliminó

    Relaciones:
    - categoria_id: clave foránea hacia la tabla categorias
    - categoria: relación ORM hacia el modelo Categoria

    ------------------------------------------------------------------
    Índices de optimización (Tarea 20)
    ------------------------------------------------------------------

    index en name:
        Optimiza consultas de búsqueda por nombre de producto.
        Ejemplo:
        SELECT * FROM items WHERE name = 'Caja Premium'

    index en eliminado:
        Optimiza consultas que filtran solo items activos.
        Ejemplo:
        SELECT * FROM items WHERE eliminado = false

    índice compuesto (name, eliminado):
        Optimiza búsquedas comunes en la API donde filtramos por nombre
        pero solo queremos items activos.

        Ejemplo:
        SELECT * FROM items
        WHERE name = 'Caja Premium'
        AND eliminado = false
    """

    __tablename__ = "items"

    # Índice compuesto para optimizar búsquedas frecuentes
    __table_args__ = (
        Index("ix_items_name_eliminado", "name", "eliminado"),
    )

    # -------------------------
    # Identificación básica
    # -------------------------

    id = Column(Integer, primary_key=True, index=True)

    # -------------------------
    # Información del item
    # -------------------------

    name = Column(String(200), nullable=False, index=True)
    description = Column(String(500), nullable=True)

    price = Column(Float, nullable=False)

    # SKU legacy del sistema
    sku = Column(String(50), nullable=True, unique=True, index=True)

    # SKU validado (AB-1234)
    codigo_sku = Column(String(20), nullable=True, index=True)

    stock = Column(Integer, nullable=False, default=0)

    proveedor = Column(String(255), nullable=True)

    # -------------------------
    # Relación con Categoría
    # -------------------------

    # Clave foránea hacia la tabla categorias
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)

    # Relación ORM:
    # muchos items pueden pertenecer a una categoría
    categoria = relationship("Categoria", back_populates="items")

    # -------------------------
    # Soft delete
    # -------------------------

    eliminado = Column(Boolean, nullable=False, default=False, index=True)
    eliminado_en = Column(DateTime, nullable=True)

    # -------------------------
    # Metadata
    # -------------------------

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )