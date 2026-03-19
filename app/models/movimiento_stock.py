from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database.database import Base


class MovimientoStock(Base):
    """
    Tabla de auditoría para transferencias de stock entre items.

    Cada registro representa una transferencia realizada y debe persistirse
    dentro de la misma transacción que modifica el stock.
    """

    __tablename__ = "movimientos_stock"

    id = Column(Integer, primary_key=True, index=True)

    item_origen_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    item_destino_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)

    cantidad = Column(Integer, nullable=False)
    usuario = Column(String(100), nullable=False, default="system")

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
