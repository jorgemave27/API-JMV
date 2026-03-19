"""
RabbitMQ Producer
Publica eventos hacia el broker para desacoplar servicios.
"""

import json

import aio_pika


class RabbitMQProducer:
    """
    Productor RabbitMQ para publicación de eventos de dominio.
    """

    def __init__(self, url: str):
        self.url = url
        self.connection = None
        self.channel = None

    async def connect(self):
        """
        Conectar al broker RabbitMQ.
        """
        if self.connection and not self.connection.is_closed:
            return

        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()

    async def publish(self, exchange: str, routing_key: str, message: dict):
        """
        Publicar un evento en un exchange tipo topic.
        """
        if not self.channel:
            await self.connect()

        exchange_obj = await self.channel.declare_exchange(
            exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        await exchange_obj.publish(
            aio_pika.Message(
                body=json.dumps(message).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=routing_key,
        )

    async def close(self):
        """
        Cerrar conexión con RabbitMQ.
        """
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
