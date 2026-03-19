"""
Configuración inicial de RabbitMQ.

Define exchanges, colas y bindings del sistema.
"""

import aio_pika

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"


async def setup_messaging():
    """
    Declara exchange topic y colas de eventos de items.
    """
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()

    # -----------------------------------------------------
    # Exchange principal de eventos de items
    # -----------------------------------------------------
    exchange = await channel.declare_exchange(
        "items_events",
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )

    # -----------------------------------------------------
    # Colas por tipo de evento
    # -----------------------------------------------------
    creado = await channel.declare_queue("items.creado", durable=True)
    actualizado = await channel.declare_queue("items.actualizado", durable=True)
    eliminado = await channel.declare_queue("items.eliminado", durable=True)

    # -----------------------------------------------------
    # Bindings
    # -----------------------------------------------------
    await creado.bind(exchange, routing_key="items.creado")
    await actualizado.bind(exchange, routing_key="items.actualizado")
    await eliminado.bind(exchange, routing_key="items.eliminado")

    await connection.close()
