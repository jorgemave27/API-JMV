from __future__ import annotations

# =====================================================
# IMPORTS
# =====================================================

import uuid

import stripe

from app.core.config import settings


# =====================================================
# CONFIGURACIÓN GLOBAL STRIPE
# =====================================================
stripe.api_key = settings.STRIPE_SECRET_KEY


# =====================================================
# HELPERS
# =====================================================
def generate_idempotency_key() -> str:
    """
    Genera una clave única de idempotencia para evitar
    cobros duplicados al reintentar la misma operación.
    """
    return str(uuid.uuid4())


# =====================================================
# CREAR PAYMENT INTENT
# =====================================================
def create_payment_intent(
    *,
    amount: int,
    currency: str = "mxn",
    metadata: dict | None = None,
    idempotency_key: str | None = None,
):
    """
    Crea un PaymentIntent en Stripe.

    IMPORTANTE:
    - amount se manda en la unidad mínima de la moneda.
      Ejemplo MXN 100.00 -> 10000

    🔥 FIX CLAVE:
    - allow_redirects="never" evita que Stripe exija return_url
      cuando hacemos pruebas puramente backend con pm_card_visa
    """
    metadata = metadata or {}
    idempotency_key = idempotency_key or generate_idempotency_key()

    intent = stripe.PaymentIntent.create(
        amount=amount,
        currency=currency,
        metadata=metadata,
        automatic_payment_methods={
            "enabled": True,
            "allow_redirects": "never",
        },
        idempotency_key=idempotency_key,
    )

    return intent, idempotency_key


# =====================================================
# CONFIRMAR PAYMENT INTENT NORMAL
# =====================================================
def confirm_payment(payment_intent_id: str):
    """
    Confirma un PaymentIntent ya existente.
    """
    return stripe.PaymentIntent.confirm(payment_intent_id)


# =====================================================
# CONFIRMAR PAYMENT INTENT EN TEST MODE
# =====================================================
def confirm_payment_test(payment_intent_id: str):
    """
    Fuerza el cobro del PaymentIntent usando un método de pago
    de prueba oficial de Stripe para validación end-to-end.
    """
    return stripe.PaymentIntent.confirm(
        payment_intent_id,
        payment_method="pm_card_visa",
    )


# =====================================================
# OBTENER PAYMENT INTENT
# =====================================================
def retrieve_payment_intent(payment_intent_id: str):
    """
    Recupera el estado actual del PaymentIntent directamente
    desde Stripe.
    """
    return stripe.PaymentIntent.retrieve(payment_intent_id)


# =====================================================
# REEMBOLSAR PAYMENT INTENT
# =====================================================
def refund_payment(payment_intent_id: str):
    """
    Genera un reembolso sobre un PaymentIntent ya cobrado.
    """
    return stripe.Refund.create(payment_intent=payment_intent_id)


# =====================================================
# LISTAR PAYMENT INTENTS
# =====================================================
def list_payment_intents(limit: int = 100):
    """
    Lista PaymentIntents en Stripe.
    Sirve para reconciliación posterior.
    """
    return stripe.PaymentIntent.list(limit=limit)