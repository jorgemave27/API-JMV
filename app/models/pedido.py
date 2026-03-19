from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database.database import Base


class Pedido(Base):
    """
    Modelo local de Pedido para la saga distribuida.

    Esta tabla representa el paso inicial de la transacción distribuida.
    La saga crea el pedido primero y luego dispara el resto de pasos:
    - reservar stock
    - cobrar pago
    - notificar cliente

    Estados sugeridos:
    - PENDIENTE
    - CONFIRMADO
    - CANCELADO
    """

    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)

    # UUID de la saga para correlacionar todos los eventos
    saga_id = Column(String(100), nullable=False, unique=True, index=True)

    # Datos mínimos del pedido
    usuario_id = Column(Integer, nullable=False, index=True)
    item_id = Column(Integer, nullable=False, index=True)
    cantidad = Column(Integer, nullable=False)
    monto_total = Column(Float, nullable=False)
    email_cliente = Column(String(255), nullable=False)

    # Estado del pedido dentro del flujo de negocio
    estado = Column(String(50), nullable=False, default="PENDIENTE", index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )