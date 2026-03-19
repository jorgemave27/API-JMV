from __future__ import annotations

import json
import os

import aio_pika


def get_rabbitmq_url() -> str:
    """
    Resuelve la URL de RabbitMQ desde variable de entorno.
    No depende de config.py para no romper tu proyecto actual.
    """
    return os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


class RabbitMQClient:
    """
    Cliente mínimo para publicar mensajes JSON en colas durables.
    """

    def __init__(self, url: str | None = None):
        self.url = url or get_rabbitmq_url()

    async def publish(self, queue_name: str, message: dict) -> None:
        connection = await aio_pika.connect_robust(self.url)
        try:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)

            queue = await channel.declare_queue(queue_name, durable=True)

            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message, default=str).encode("utf-8"),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                ),
                routing_key=queue.name,
            )
        finally:
            await connection.close()