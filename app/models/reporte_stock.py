from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ReporteStock(Base):
    __tablename__ = "reportes_stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False, default="stock_bajo")
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    umbral: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    contenido: Mapped[list | dict] = mapped_column(JSON, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
