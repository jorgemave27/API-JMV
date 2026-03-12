"""
RabbitMQ Consumer
Escucha colas y ejecuta callbacks cuando llegan mensajes.
"""

import aio_pika


class RabbitMQConsumer:
    """
    Consumidor RabbitMQ.

    Responsabilidades:
    - Conectar al broker
    - Declarar cola durable
    - Consumir mensajes
    - Ejecutar callback asíncrono
    """

    def __init__(self, url: str = "amqp://guest:guest@localhost:5672/"):
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

    async def start(self, queue_name: str, callback):
        """
        Iniciar consumo de una cola durable.
        """
        if not self.channel:
            await self.connect()

        queue = await self.channel.declare_queue(queue_name, durable=True)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    await callback(message.body)