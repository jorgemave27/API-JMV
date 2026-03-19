"""
Configuración inicial de RabbitMQ.

Mantiene:
- exchange y colas legacy de items

Agrega:
- colas durables para la saga de pedidos
"""

from __future__ import annotations

import os

import aio_pika

from app.saga.constants import SagaQueue


def get_rabbitmq_url() -> str:
    """
    Obtiene la URL de RabbitMQ desde entorno.
    Si no existe, usa localhost para desarrollo local.
    """
    return os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


async def setup_messaging() -> None:
    """
    Declara:
    1) Exchange + colas legacy de items
    2) Colas de saga distribuida
    """
    connection = await aio_pika.connect_robust(get_rabbitmq_url())

    try:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        # =====================================================
        # LEGACY: exchange principal de eventos de items
        # =====================================================
        exchange = await channel.declare_exchange(
            "items_events",
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        # -----------------------------------------------------
        # Colas legacy por tipo de evento
        # -----------------------------------------------------
        creado = await channel.declare_queue("items.creado", durable=True)
        actualizado = await channel.declare_queue("items.actualizado", durable=True)
        eliminado = await channel.declare_queue("items.eliminado", durable=True)

        # -----------------------------------------------------
        # Bindings legacy
        # -----------------------------------------------------
        await creado.bind(exchange, routing_key="items.creado")
        await actualizado.bind(exchange, routing_key="items.actualizado")
        await eliminado.bind(exchange, routing_key="items.eliminado")

        # =====================================================
        # NUEVO: colas durables para saga de pedidos
        # =====================================================
        saga_queues = [
            SagaQueue.CREATE_PEDIDO,
            SagaQueue.RESERVAR_STOCK,
            SagaQueue.COBRAR_PAGO,
            SagaQueue.NOTIFICAR_CLIENTE,
            SagaQueue.CONFIRMAR_PEDIDO,
            SagaQueue.COMPENSAR_STOCK,
            SagaQueue.CANCELAR_PEDIDO,
        ]

        for queue_name in saga_queues:
            await channel.declare_queue(queue_name, durable=True)

        print("✅ RabbitMQ configurado correctamente")
        print("✅ Colas legacy de items listas")
        print("✅ Colas de saga listas")

    finally:
        await connection.close()