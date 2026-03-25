from __future__ import annotations

# =====================================================
# IMPORTS
# =====================================================

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

# 🔥 Base de tu proyecto (NO cambiar)
from app.database.database import Base


# =====================================================
# MODELO PAGO
# =====================================================
class Pago(Base):
    """
    Modelo de pagos integrado con Stripe.

    🔥 PROPÓSITO:
    - Registrar TODO el ciclo de vida del pago
    - Mantener consistencia con Stripe (source of truth externo)
    - Permitir auditoría y reconciliación futura

    =====================================================
    🔁 FLUJO DE VIDA:
    =====================================================

    1. Se crea el pedido (tabla pedidos)
    2. Se crea el pago (estado: pendiente)
    3. Stripe procesa el pago
    4. Webhook actualiza estado:

        pendiente → pagado
        pendiente → fallido
        pagado → reembolsado

    =====================================================
    🔒 SEGURIDAD:
    =====================================================

    - NO guardamos datos de tarjeta ❌
    - Solo IDs de Stripe (PCI compliant)
    - Idempotency evita doble cobro

    =====================================================
    🔁 RELACIÓN:
    =====================================================

    Pago → Pedido (por pedido_id)

    """

    __tablename__ = "pagos"

    # =====================================================
    # ID LOCAL
    # =====================================================
    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="ID interno del pago"
    )

    # =====================================================
    # RELACIÓN CON PEDIDO
    # =====================================================
    pedido_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="ID del pedido asociado"
    )

    # =====================================================
    # STRIPE
    # =====================================================
    stripe_payment_intent_id = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="ID del PaymentIntent en Stripe"
    )

    # =====================================================
    # MONTO
    # =====================================================
    monto = Column(
        Float,
        nullable=False,
        comment="Monto del pago (en moneda principal, ej: MXN)"
    )

    moneda = Column(
        String(10),
        nullable=False,
        default="mxn",
        comment="Moneda del pago"
    )

    # =====================================================
    # ESTADO DEL PAGO
    # =====================================================
    estado = Column(
        String(50),
        nullable=False,
        default="pendiente",
        index=True,
        comment="""
        Estados posibles:

        - pendiente
        - pagado
        - fallido
        - reembolsado
        """
    )

    # =====================================================
    # IDEMPOTENCIA (🔥 CRÍTICO)
    # =====================================================
    idempotency_key = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="""
        Clave única para evitar doble cobro.

        Si el cliente reintenta el pago:
        → Stripe usa la misma key
        → NO se genera un nuevo cargo
        """
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Fecha de creación del pago"
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Última actualización del pago"
    )