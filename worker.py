import asyncio
import json

from app.messaging.consumer import RabbitMQConsumer


async def handle_message(body: bytes):
    """
    Procesa mensajes consumidos desde RabbitMQ.
    """
    payload = json.loads(body.decode("utf-8"))
    print("Evento recibido:", payload)


async def main():
    """
    Inicia worker sobre la cola de items creados.
    """
    consumer = RabbitMQConsumer()
    await consumer.start("items.creado", handle_message)


if __name__ == "__main__":
    asyncio.run(main())