from __future__ import annotations

# =====================================================
# IMPORTS
# =====================================================

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.responses import error_response
from app.core.security import require_role, verify_api_key
from app.database.database import get_db
from app.models.pago import Pago
from app.models.pedido import Pedido
from app.payments.stripe_service import (
    confirm_payment_test,
    create_payment_intent,
    refund_payment,
    retrieve_payment_intent,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =====================================================
# HELPERS DE ESTADO
# =====================================================
def apply_payment_success(db: Session, pago: Pago) -> None:
    """
    Marca el pago como exitoso y confirma el pedido asociado.
    """
    pago.estado = "pagado"

    pedido = db.query(Pedido).filter(Pedido.id == pago.pedido_id).first()
    if pedido:
        pedido.estado = "CONFIRMADO"

    db.commit()


def apply_payment_failed(db: Session, pago: Pago) -> None:
    """
    Marca el pago como fallido y cancela el pedido asociado.
    """
    pago.estado = "fallido"

    pedido = db.query(Pedido).filter(Pedido.id == pago.pedido_id).first()
    if pedido:
        pedido.estado = "CANCELADO"

    db.commit()


def apply_payment_refunded(db: Session, pago: Pago) -> None:
    """
    Marca el pago como reembolsado y cancela el pedido asociado.
    """
    pago.estado = "reembolsado"

    pedido = db.query(Pedido).filter(Pedido.id == pago.pedido_id).first()
    if pedido:
        pedido.estado = "CANCELADO"

    db.commit()


# =====================================================
# CREAR PAGO PARA UN PEDIDO
# =====================================================
@router.post(
    "/pagos/crear",
    summary="Crear intento de pago con Stripe",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
def crear_pago(
    pedido_id: int,
    db: Session = Depends(get_db),
):
    """
    Crea un PaymentIntent en Stripe y registra el pago localmente.
    """

    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()

    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado",
        )

    pago_existente_pagado = (
        db.query(Pago)
        .filter(Pago.pedido_id == pedido.id, Pago.estado == "pagado")
        .first()
    )

    if pago_existente_pagado:
        return error_response(
            status_code=400,
            message="El pedido ya cuenta con un pago exitoso",
            data={
                "pedido_id": pedido.id,
                "pago_id": pago_existente_pagado.id,
                "estado": pago_existente_pagado.estado,
            },
        )

    try:
        intent, idempotency_key = create_payment_intent(
            amount=int(round(pedido.monto_total * 100)),
            currency="mxn",
            metadata={
                "pedido_id": str(pedido.id),
                "saga_id": str(pedido.saga_id),
                "email_cliente": pedido.email_cliente,
            },
        )

        pago = Pago(
            pedido_id=pedido.id,
            stripe_payment_intent_id=intent.id,
            monto=pedido.monto_total,
            moneda="mxn",
            estado="pendiente",
            idempotency_key=idempotency_key,
        )

        db.add(pago)
        db.commit()
        db.refresh(pago)

        logger.info(
            "Pago creado | pedido_id=%s | pago_id=%s | payment_intent=%s",
            pedido.id,
            pago.id,
            intent.id,
        )

        return {
            "success": True,
            "message": "Intento de pago creado exitosamente",
            "data": {
                "pago_id": pago.id,
                "pedido_id": pedido.id,
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "estado": pago.estado,
            },
            "metadata": {},
        }

    except Exception as exc:
        db.rollback()
        logger.error("Error creando pago Stripe: %s", exc, exc_info=True)

        return error_response(
            status_code=500,
            message="Error al crear el intento de pago",
            data={"error": str(exc)},
        )


# =====================================================
# CONFIRMAR PAGO EXACTO EN TEST MODE (E2E REAL)
# =====================================================
@router.post(
    "/pagos/{pago_id}/confirm-test",
    summary="Confirmar pago exacto en Stripe Test Mode",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
def confirmar_pago_test(
    pago_id: int,
    db: Session = Depends(get_db),
):
    """
    Confirma el MISMO PaymentIntent registrado en la tabla pagos
    usando el método de prueba oficial de Stripe.

    Esto permite validar la tarea end-to-end de verdad.
    """

    pago = db.query(Pago).filter(Pago.id == pago_id).first()

    if not pago:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado",
        )

    if pago.estado == "pagado":
        return {
            "success": True,
            "message": "El pago ya estaba confirmado",
            "data": {
                "pago_id": pago.id,
                "payment_intent_id": pago.stripe_payment_intent_id,
                "estado": pago.estado,
            },
            "metadata": {},
        }

    try:
        intent = confirm_payment_test(pago.stripe_payment_intent_id)

        logger.info(
            "Confirmación test lanzada | pago_id=%s | payment_intent_id=%s | stripe_status=%s",
            pago.id,
            pago.stripe_payment_intent_id,
            intent.get("status"),
        )

        return {
            "success": True,
            "message": "Confirmación de pago enviada a Stripe",
            "data": {
                "pago_id": pago.id,
                "payment_intent_id": pago.stripe_payment_intent_id,
                "stripe_status": intent.get("status"),
                "estado_local": pago.estado,
            },
            "metadata": {},
        }

    except Exception as exc:
        logger.error("Error confirmando pago test: %s", exc, exc_info=True)
        return error_response(
            status_code=500,
            message="Error al confirmar el pago de prueba",
            data={"error": str(exc)},
        )


# =====================================================
# SINCRONIZAR ESTADO DESDE STRIPE
# =====================================================
@router.post(
    "/pagos/{pago_id}/sync",
    summary="Sincronizar estado del pago desde Stripe",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin", "editor"))],
)
def sincronizar_pago(
    pago_id: int,
    db: Session = Depends(get_db),
):
    """
    Consulta Stripe directamente para el MISMO PaymentIntent
    y actualiza la BD local.

    Esto cierra la validación aunque el webhook tarde unos segundos.
    """

    pago = db.query(Pago).filter(Pago.id == pago_id).first()

    if not pago:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado",
        )

    try:
        intent = retrieve_payment_intent(pago.stripe_payment_intent_id)
        stripe_status = intent.get("status")

        if stripe_status == "succeeded":
            apply_payment_success(db, pago)
        elif stripe_status in {"requires_payment_method", "canceled"}:
            apply_payment_failed(db, pago)

        db.refresh(pago)

        pedido = db.query(Pedido).filter(Pedido.id == pago.pedido_id).first()

        return {
            "success": True,
            "message": "Pago sincronizado correctamente",
            "data": {
                "pago_id": pago.id,
                "payment_intent_id": pago.stripe_payment_intent_id,
                "stripe_status": stripe_status,
                "estado_pago": pago.estado,
                "estado_pedido": pedido.estado if pedido else None,
            },
            "metadata": {},
        }

    except Exception as exc:
        logger.error("Error sincronizando pago: %s", exc, exc_info=True)
        return error_response(
            status_code=500,
            message="Error al sincronizar el pago con Stripe",
            data={"error": str(exc)},
        )


# =====================================================
# REEMBOLSAR PAGO
# =====================================================
@router.post(
    "/pagos/{pago_id}/refund",
    summary="Reembolsar pago en Stripe",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin"))],
)
def reembolsar_pago(
    pago_id: int,
    db: Session = Depends(get_db),
):
    """
    Lanza un reembolso en Stripe para un pago existente.
    """

    pago = db.query(Pago).filter(Pago.id == pago_id).first()

    if not pago:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado",
        )

    if pago.estado != "pagado":
        return error_response(
            status_code=400,
            message="Solo se pueden reembolsar pagos en estado pagado",
            data={
                "pago_id": pago.id,
                "estado_actual": pago.estado,
            },
        )

    try:
        refund = refund_payment(pago.stripe_payment_intent_id)

        logger.info(
            "Refund solicitado | pago_id=%s | refund_id=%s",
            pago.id,
            refund.get("id"),
        )

        return {
            "success": True,
            "message": "Reembolso solicitado exitosamente",
            "data": {
                "pago_id": pago.id,
                "payment_intent_id": pago.stripe_payment_intent_id,
                "refund_id": refund.get("id"),
                "refund_status": refund.get("status"),
            },
            "metadata": {},
        }

    except Exception as exc:
        logger.error("Error refund Stripe: %s", exc, exc_info=True)

        return error_response(
            status_code=500,
            message="Error al solicitar el reembolso",
            data={"error": str(exc)},
        )


# =====================================================
# WEBHOOK STRIPE
# =====================================================
@router.post(
    "/pagos/webhook",
    summary="Webhook de Stripe",
)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Recibe eventos asíncronos de Stripe y actualiza la BD local.
    """

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload inválido",
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firma de webhook inválida",
        )
    except Exception as exc:
        logger.error("Error validando webhook Stripe: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook inválido",
        )

    event_type = event["type"]
    obj = event["data"]["object"]

    logger.info("Webhook Stripe recibido | event_type=%s", event_type)

    if event_type == "payment_intent.succeeded":
        payment_intent_id = obj["id"]

        pago = (
            db.query(Pago)
            .filter(Pago.stripe_payment_intent_id == payment_intent_id)
            .first()
        )

        if pago:
            apply_payment_success(db, pago)

            logger.info(
                "Pago confirmado por webhook | pago_id=%s | pedido_id=%s",
                pago.id,
                pago.pedido_id,
            )

    elif event_type == "payment_intent.payment_failed":
        payment_intent_id = obj["id"]

        pago = (
            db.query(Pago)
            .filter(Pago.stripe_payment_intent_id == payment_intent_id)
            .first()
        )

        if pago:
            apply_payment_failed(db, pago)

            logger.warning(
                "Pago fallido por webhook | pago_id=%s | pedido_id=%s",
                pago.id,
                pago.pedido_id,
            )

    elif event_type == "charge.refunded":
        payment_intent_id = obj.get("payment_intent")

        if payment_intent_id:
            pago = (
                db.query(Pago)
                .filter(Pago.stripe_payment_intent_id == payment_intent_id)
                .first()
            )

            if pago:
                apply_payment_refunded(db, pago)

                logger.info(
                    "Pago reembolsado por webhook | pago_id=%s | pedido_id=%s",
                    pago.id,
                    pago.pedido_id,
                )

    return {"status": "ok"}