from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaProducer

from app.core.config import settings
from app.schemas.domain_event import DomainEvent

logger = logging.getLogger(__name__)


async def _publish_event_async(event: DomainEvent) -> None:
    """
    Publica un evento en Kafka usando AIOKafkaProducer.

    Nota:
    - Se crea un producer por publicación para mantener la integración simple
      y compatible con endpoints sync actuales.
    - Más adelante se puede optimizar con un producer persistente en lifespan.
    """
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        client_id=settings.KAFKA_CLIENT_ID,
        value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
        key_serializer=lambda key: key.encode("utf-8") if key else None,
    )

    try:
        await producer.start()

        await producer.send_and_wait(
            topic=settings.KAFKA_EVENTS_TOPIC,
            key=event.aggregate_id,
            value=event.model_dump(mode="json"),
        )

    finally:
        try:
            await producer.stop()
        except Exception:
            logger.exception("Error al cerrar Kafka producer")


def publish_domain_event(event: DomainEvent) -> None:
    """
    Publica un evento de dominio en Kafka de forma segura.

    Diseño:
    - Si Kafka falla, NO rompe la operación principal del endpoint.
    - Solo deja traza en logs.
    - Esto mantiene la UX y los tests estables.

    Importante:
    - Esta versión usa asyncio.run porque tus endpoints actuales
      son principalmente síncronos (`def`).
    """
    if not settings.KAFKA_ENABLED:
        logger.info(
            "Kafka deshabilitado por configuración. Evento omitido.",
            extra={"event_type": event.event_type},
        )
        return

    try:
        asyncio.run(_publish_event_async(event))
        logger.info(
            "Evento publicado en Kafka",
            extra={
                "event_id": event.event_id,
                "event_type": event.event_type,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": event.aggregate_id,
                "topic": settings.KAFKA_EVENTS_TOPIC,
            },
        )
    except Exception as exc:
        logger.warning(
            "No se pudo publicar evento en Kafka: %s",
            exc,
            extra={
                "event_type": event.event_type,
                "aggregate_id": event.aggregate_id,
                "topic": settings.KAFKA_EVENTS_TOPIC,
            },
        )
