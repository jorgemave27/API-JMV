from __future__ import annotations

import asyncio
import json

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.database.database import SessionLocal
from app.messaging.rabbitmq_client import RabbitMQClient, get_rabbitmq_url
from app.models.item import Item
from app.models.pedido import Pedido
from app.saga.constants import PedidoEstado, SagaQueue, SagaStatus, SagaStep
from app.saga.repository import SagaRepository


async def _process_create_pedido(message_data: dict) -> None:
    """
    Paso 1: crear pedido en BD local.
    """
    db = SessionLocal()
    try:
        repo = SagaRepository(db)

        saga_id = message_data["saga_id"]
        step = SagaStep.CREATE_PEDIDO

        if repo.already_processed(saga_id, step):
            print(f"↩️ CREATE_PEDIDO ya procesado para saga_id={saga_id}")
            return

        repo.create_step(saga_id, step, message_data)

        pedido = Pedido(
            saga_id=saga_id,
            usuario_id=message_data["usuario_id"],
            item_id=message_data["item_id"],
            cantidad=message_data["cantidad"],
            monto_total=message_data["monto_total"],
            email_cliente=message_data["email_cliente"],
            estado=PedidoEstado.PENDIENTE,
        )
        db.add(pedido)
        db.commit()
        db.refresh(pedido)

        repo.update_status(saga_id, step, SagaStatus.COMPLETED)

        rabbit = RabbitMQClient()
        await rabbit.publish(SagaQueue.RESERVAR_STOCK, message_data)

        print(f"✅ Pedido creado | saga_id={saga_id} | pedido_id={pedido.id}")
    except Exception as exc:
        db.rollback()
        repo = SagaRepository(db)
        repo.update_status(message_data["saga_id"], SagaStep.CREATE_PEDIDO, SagaStatus.FAILED, str(exc))
        raise
    finally:
        db.close()


async def _process_reservar_stock(message_data: dict) -> None:
    """
    Paso 2: reservar stock del item.
    Si falla aquí, se cancela el pedido directamente.
    """
    db = SessionLocal()
    try:
        repo = SagaRepository(db)

        saga_id = message_data["saga_id"]
        step = SagaStep.RESERVAR_STOCK

        if repo.already_processed(saga_id, step):
            print(f"↩️ RESERVAR_STOCK ya procesado para saga_id={saga_id}")
            return

        repo.create_step(saga_id, step, message_data)

        pedido = db.query(Pedido).filter(Pedido.saga_id == saga_id).first()
        if pedido is None:
            raise RuntimeError("Pedido no encontrado para reservar stock")

        item = db.query(Item).filter(Item.id == pedido.item_id).first()
        if item is None:
            raise RuntimeError("Item no encontrado para reservar stock")

        if message_data.get("force_stock_fail", False):
            raise RuntimeError("Falla forzada en RESERVAR_STOCK")

        if item.stock < pedido.cantidad:
            raise RuntimeError(
                f"Stock insuficiente. stock_actual={item.stock}, cantidad={pedido.cantidad}"
            )

        item.stock -= pedido.cantidad
        db.commit()

        repo.update_status(saga_id, step, SagaStatus.COMPLETED)

        rabbit = RabbitMQClient()
        await rabbit.publish(SagaQueue.COBRAR_PAGO, message_data)

        print(f"✅ Stock reservado | saga_id={saga_id} | item_id={item.id}")
    except Exception as exc:
        db.rollback()
        repo = SagaRepository(db)
        repo.update_status(message_data["saga_id"], SagaStep.RESERVAR_STOCK, SagaStatus.FAILED, str(exc))

        rabbit = RabbitMQClient()
        await rabbit.publish(SagaQueue.CANCELAR_PEDIDO, message_data)

        print(f"❌ Falló RESERVAR_STOCK | saga_id={message_data['saga_id']} | error={exc}")
    finally:
        db.close()


async def _process_cobrar_pago(message_data: dict) -> None:
    """
    Paso 3: cobro de pago simulado.
    Si falla, se dispara compensación de stock y luego cancelación de pedido.
    """
    db = SessionLocal()
    try:
        repo = SagaRepository(db)

        saga_id = message_data["saga_id"]
        step = SagaStep.COBRAR_PAGO

        if repo.already_processed(saga_id, step):
            print(f"↩️ COBRAR_PAGO ya procesado para saga_id={saga_id}")
            return

        repo.create_step(saga_id, step, message_data)

        if message_data.get("force_payment_fail", False):
            raise RuntimeError("Falla forzada en COBRAR_PAGO")

        # Simulación simple de cobro exitoso
        repo.update_status(saga_id, step, SagaStatus.COMPLETED)

        rabbit = RabbitMQClient()
        await rabbit.publish(SagaQueue.NOTIFICAR_CLIENTE, message_data)

        print(f"✅ Pago cobrado | saga_id={saga_id}")
    except Exception as exc:
        db.rollback()
        repo = SagaRepository(db)
        repo.update_status(message_data["saga_id"], SagaStep.COBRAR_PAGO, SagaStatus.FAILED, str(exc))

        rabbit = RabbitMQClient()
        await rabbit.publish(SagaQueue.COMPENSAR_STOCK, message_data)

        print(f"❌ Falló COBRAR_PAGO | saga_id={message_data['saga_id']} | error={exc}")
    finally:
        db.close()


async def _process_notificar_cliente(message_data: dict) -> None:
    """
    Paso 4: notificación simulada.
    Si falla aquí, para esta versión se cancela la saga completa con compensación,
    para que puedas probar más escenarios.
    """
    db = SessionLocal()
    try:
        repo = SagaRepository(db)

        saga_id = message_data["saga_id"]
        step = SagaStep.NOTIFICAR_CLIENTE

        if repo.already_processed(saga_id, step):
            print(f"↩️ NOTIFICAR_CLIENTE ya procesado para saga_id={saga_id}")
            return

        repo.create_step(saga_id, step, message_data)

        if message_data.get("force_notification_fail", False):
            raise RuntimeError("Falla forzada en NOTIFICAR_CLIENTE")

        # Notificación simulada
        print(
            f"📧 Email simulado enviado a {message_data['email_cliente']} | saga_id={saga_id}"
        )

        repo.update_status(saga_id, step, SagaStatus.COMPLETED)

        rabbit = RabbitMQClient()
        await rabbit.publish(SagaQueue.CONFIRMAR_PEDIDO, message_data)

        print(f"✅ Cliente notificado | saga_id={saga_id}")
    except Exception as exc:
        db.rollback()
        repo = SagaRepository(db)
        repo.update_status(message_data["saga_id"], SagaStep.NOTIFICAR_CLIENTE, SagaStatus.FAILED, str(exc))

        rabbit = RabbitMQClient()
        await rabbit.publish(SagaQueue.COMPENSAR_STOCK, message_data)

        print(f"❌ Falló NOTIFICAR_CLIENTE | saga_id={message_data['saga_id']} | error={exc}")
    finally:
        db.close()


async def _process_confirmar_pedido(message_data: dict) -> None:
    """
    Paso final feliz: confirmar pedido.
    """
    db = SessionLocal()
    try:
        repo = SagaRepository(db)

        saga_id = message_data["saga_id"]
        step = SagaStep.CONFIRMAR_PEDIDO

        if repo.already_processed(saga_id, step):
            print(f"↩️ CONFIRMAR_PEDIDO ya procesado para saga_id={saga_id}")
            return

        repo.create_step(saga_id, step, message_data)

        pedido = db.query(Pedido).filter(Pedido.saga_id == saga_id).first()
        if pedido is None:
            raise RuntimeError("Pedido no encontrado para confirmar")

        pedido.estado = PedidoEstado.CONFIRMADO
        db.commit()

        repo.update_status(saga_id, step, SagaStatus.COMPLETED)

        print(f"✅ Pedido confirmado | saga_id={saga_id} | pedido_id={pedido.id}")
    except Exception as exc:
        db.rollback()
        repo = SagaRepository(db)
        repo.update_status(message_data["saga_id"], SagaStep.CONFIRMAR_PEDIDO, SagaStatus.FAILED, str(exc))
        raise
    finally:
        db.close()


async def _process_compensar_stock(message_data: dict) -> None:
    """
    Compensación: devolver stock reservado.
    Después dispara CANCELAR_PEDIDO.
    """
    db = SessionLocal()
    try:
        repo = SagaRepository(db)

        saga_id = message_data["saga_id"]
        step = SagaStep.COMPENSAR_STOCK

        if repo.already_processed(saga_id, step):
            print(f"↩️ COMPENSAR_STOCK ya procesado para saga_id={saga_id}")
            return

        repo.create_step(saga_id, step, message_data)
        repo.update_status(saga_id, step, SagaStatus.COMPENSATING)

        pedido = db.query(Pedido).filter(Pedido.saga_id == saga_id).first()
        if pedido is None:
            raise RuntimeError("Pedido no encontrado para compensar stock")

        item = db.query(Item).filter(Item.id == pedido.item_id).first()
        if item is None:
            raise RuntimeError("Item no encontrado para compensar stock")

        item.stock += pedido.cantidad
        db.commit()

        repo.update_status(saga_id, step, SagaStatus.COMPENSATED)

        rabbit = RabbitMQClient()
        await rabbit.publish(SagaQueue.CANCELAR_PEDIDO, message_data)

        print(f"♻️ Stock compensado | saga_id={saga_id} | item_id={item.id}")
    except Exception as exc:
        db.rollback()
        repo = SagaRepository(db)
        repo.update_status(message_data["saga_id"], SagaStep.COMPENSAR_STOCK, SagaStatus.FAILED, str(exc))
        raise
    finally:
        db.close()


async def _process_cancelar_pedido(message_data: dict) -> None:
    """
    Compensación final: cancelar pedido.
    """
    db = SessionLocal()
    try:
        repo = SagaRepository(db)

        saga_id = message_data["saga_id"]
        step = SagaStep.CANCELAR_PEDIDO

        if repo.already_processed(saga_id, step):
            print(f"↩️ CANCELAR_PEDIDO ya procesado para saga_id={saga_id}")
            return

        repo.create_step(saga_id, step, message_data)
        repo.update_status(saga_id, step, SagaStatus.COMPENSATING)

        pedido = db.query(Pedido).filter(Pedido.saga_id == saga_id).first()
        if pedido is None:
            raise RuntimeError("Pedido no encontrado para cancelar")

        pedido.estado = PedidoEstado.CANCELADO
        db.commit()

        repo.update_status(saga_id, step, SagaStatus.COMPENSATED)

        print(f"🛑 Pedido cancelado | saga_id={saga_id} | pedido_id={pedido.id}")
    except Exception as exc:
        db.rollback()
        repo = SagaRepository(db)
        repo.update_status(message_data["saga_id"], SagaStep.CANCELAR_PEDIDO, SagaStatus.FAILED, str(exc))
        raise
    finally:
        db.close()


async def _dispatch(queue_name: str, message_data: dict) -> None:
    """
    Router interno por cola.
    """
    if queue_name == SagaQueue.CREATE_PEDIDO:
        await _process_create_pedido(message_data)
        return

    if queue_name == SagaQueue.RESERVAR_STOCK:
        await _process_reservar_stock(message_data)
        return

    if queue_name == SagaQueue.COBRAR_PAGO:
        await _process_cobrar_pago(message_data)
        return

    if queue_name == SagaQueue.NOTIFICAR_CLIENTE:
        await _process_notificar_cliente(message_data)
        return

    if queue_name == SagaQueue.CONFIRMAR_PEDIDO:
        await _process_confirmar_pedido(message_data)
        return

    if queue_name == SagaQueue.COMPENSAR_STOCK:
        await _process_compensar_stock(message_data)
        return

    if queue_name == SagaQueue.CANCELAR_PEDIDO:
        await _process_cancelar_pedido(message_data)
        return

    raise RuntimeError(f"Queue no soportada: {queue_name}")


async def _consume_queue(channel: aio_pika.Channel, queue_name: str) -> None:
    """
    Consumidor por cola durable.
    """
    queue = await channel.declare_queue(queue_name, durable=True)

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process(requeue=False):
                payload = json.loads(message.body.decode("utf-8"))
                await _dispatch(queue_name, payload)


async def run_saga_consumers() -> None:
    """
    Levanta todos los consumers de la saga en paralelo.
    """
    connection = await aio_pika.connect_robust(get_rabbitmq_url())

    try:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        await asyncio.gather(
            _consume_queue(channel, SagaQueue.CREATE_PEDIDO),
            _consume_queue(channel, SagaQueue.RESERVAR_STOCK),
            _consume_queue(channel, SagaQueue.COBRAR_PAGO),
            _consume_queue(channel, SagaQueue.NOTIFICAR_CLIENTE),
            _consume_queue(channel, SagaQueue.CONFIRMAR_PEDIDO),
            _consume_queue(channel, SagaQueue.COMPENSAR_STOCK),
            _consume_queue(channel, SagaQueue.CANCELAR_PEDIDO),
        )
    finally:
        await connection.close()