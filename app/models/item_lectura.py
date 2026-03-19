from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ItemLectura(Base):
    """
    Modelo de lectura desnormalizado para CQRS.

    Esta tabla NO se usa para escribir.
    Solo se usa para lecturas optimizadas.
    """

    __tablename__ = "items_lectura"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Datos principales del item
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    codigo_sku: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proveedor: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Categoría aplanada
    categoria_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    categoria_nombre: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Campos calculados / desnormalizados
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    precio_con_impuesto: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Soft delete
    eliminado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    eliminado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Metadata
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
