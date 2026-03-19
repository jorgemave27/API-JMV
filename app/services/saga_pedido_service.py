from __future__ import annotations

import uuid

from app.messaging.rabbitmq_client import RabbitMQClient
from app.saga.constants import SagaQueue


async def iniciar_saga_pedido(payload: dict) -> str:
    """
    Inicia la saga publicando el primer evento.

    El pedido real NO se crea aquí.
    Se crea dentro del consumidor CREATE_PEDIDO para respetar choreography.
    """
    saga_id = str(uuid.uuid4())

    event = {
        "saga_id": saga_id,
        "usuario_id": payload["usuario_id"],
        "item_id": payload["item_id"],
        "cantidad": payload["cantidad"],
        "monto_total": payload["monto_total"],
        "email_cliente": payload["email_cliente"],
        "force_stock_fail": payload.get("force_stock_fail", False),
        "force_payment_fail": payload.get("force_payment_fail", False),
        "force_notification_fail": payload.get("force_notification_fail", False),
    }

    rabbit = RabbitMQClient()
    await rabbit.publish(SagaQueue.CREATE_PEDIDO, event)

    return saga_id