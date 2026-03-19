from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from aiokafka import AIOKafkaConsumer
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.categoria import Categoria

# ---------------------------------------------------------
# IMPORTANTE:
# Importamos Item también, aunque aquí no lo usemos directo,
# para que SQLAlchemy pueda resolver la relación de Categoria
# que referencia "Item".
# ---------------------------------------------------------
from app.models.item import Item  # noqa: F401
from app.models.item_lectura import ItemLectura
from app.services.operation_service import OperationService

logger = logging.getLogger(__name__)

engine = create_engine(settings.DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def calcular_precio_con_impuesto(price: float) -> float:
    """
    Cálculo simple para el modelo de lectura.
    """
    return round(price * 1.16, 2)


def upsert_item_projection(payload: dict) -> None:
    """
    Crea o actualiza la proyección en items_lectura.
    """
    db = SessionLocal()
    try:
        item_id = int(payload["id"])
        categoria_id = payload.get("categoria_id")

        categoria_nombre = payload.get("categoria_nombre")
        if categoria_nombre is None and categoria_id is not None:
            categoria = db.execute(select(Categoria).where(Categoria.id == categoria_id)).scalars().first()
            categoria_nombre = categoria.nombre if categoria else None

        projection = db.get(ItemLectura, item_id)
        if projection is None:
            projection = ItemLectura(id=item_id)
            db.add(projection)

        projection.name = payload.get("name")
        projection.description = payload.get("description")
        projection.price = payload.get("price", 0.0)
        projection.sku = payload.get("sku")
        projection.codigo_sku = payload.get("codigo_sku")
        projection.stock = payload.get("stock", 0)
        projection.proveedor = payload.get("proveedor")
        projection.categoria_id = categoria_id
        projection.categoria_nombre = categoria_nombre
        projection.disponible = payload.get("stock", 0) > 0
        projection.precio_con_impuesto = calcular_precio_con_impuesto(payload.get("price", 0.0))
        projection.eliminado = payload.get("eliminado", False)
        projection.eliminado_en = (
            datetime.fromisoformat(payload["eliminado_en"]) if payload.get("eliminado_en") else None
        )
        projection.created_at = datetime.fromisoformat(payload["created_at"]) if payload.get("created_at") else None
        projection.actualizado_en = datetime.utcnow()

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def consume() -> None:
    """
    Consumer Kafka que mantiene la proyección de lectura.
    """
    operation_service = OperationService()

    consumer = AIOKafkaConsumer(
        settings.KAFKA_EVENTS_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id="items-lectura-projection-consumer",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )

    await consumer.start()
    logger.info("Projection consumer iniciado")

    try:
        async for msg in consumer:
            event = msg.value
            event_type = event.get("event_type")
            payload = event.get("payload", {})
            metadata = event.get("metadata", {})
            operation_id = metadata.get("operation_id")

            if event_type in {"item.created", "item.updated", "item.deleted", "item.restored"}:
                try:
                    upsert_item_projection(payload)

                    if operation_id:
                        operation_service.complete_operation(
                            operation_id=operation_id,
                            resource_id=payload.get("id"),
                        )

                    logger.info(
                        "Proyección actualizada OK event_type=%s aggregate_id=%s",
                        event_type,
                        event.get("aggregate_id"),
                    )
                except Exception as exc:
                    logger.exception("Error actualizando proyección: %s", exc)
                    if operation_id:
                        operation_service.fail_operation(operation_id, str(exc))
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(consume())
