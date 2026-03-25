from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaProducer

from app.core.config import settings
from app.schemas.domain_event import DomainEvent

logger = logging.getLogger(__name__)


# =========================================================
# 🔥 FIX ASYNC GLOBAL
# =========================================================
def safe_async_run(coro):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        asyncio.run(coro)


# =========================================================
# ASYNC PRODUCER
# =========================================================
async def _publish_event_async(event: DomainEvent) -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        client_id=settings.KAFKA_CLIENT_ID,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
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
            logger.exception("Error cerrando Kafka producer")


# =========================================================
# PUBLIC API (FIX)
# =========================================================
def publish_domain_event(event: DomainEvent) -> None:
    """
    🔥 FIX:
    - NO usa asyncio.run directamente
    - NO rompe FastAPI
    """
    if not settings.KAFKA_ENABLED:
        return

    try:
        safe_async_run(_publish_event_async(event))  # 🔥 FIX REAL
    except Exception as exc:
        logger.warning("Kafka no disponible: %s", exc)