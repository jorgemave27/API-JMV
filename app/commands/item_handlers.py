from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.base import CommandHandler
from app.commands.items import ActualizarItemCommand, CrearItemCommand, EliminarItemCommand
from app.core.exceptions import ItemNoEncontradoError
from app.core.request_context import set_current_user_id
from app.messaging.kafka_publisher import publish_domain_event
from app.models.categoria import Categoria
from app.models.item import Item
from app.schemas.domain_event import DomainEvent
from app.schemas.item import ItemRead
from app.services.operation_service import OperationService

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """
    Resultado estándar de un command.
    """
    resource_id: int
    operation_id: str


class CrearItemHandler(CommandHandler[CrearItemCommand, CommandResult]):
    """
    Handler CQRS para crear items.
    """

    def __init__(self, db: Session, current_user_id: int | None = None, current_user_email: str | None = None):
        self.db = db
        self.current_user_id = current_user_id
        self.current_user_email = current_user_email
        self.operation_service = OperationService()

    def handle(self, command: CrearItemCommand) -> CommandResult:
        set_current_user_id(self.current_user_id)

        categoria_nombre = None
        if command.categoria_id is not None:
            categoria = (
                self.db.execute(
                    select(Categoria).where(Categoria.id == command.categoria_id)
                )
                .scalars()
                .first()
            )
            if not categoria:
                raise ValueError(f"La categoría con id={command.categoria_id} no existe")
            categoria_nombre = categoria.nombre

        item = Item(
            name=command.name,
            description=command.description,
            price=command.price,
            sku=command.sku,
            codigo_sku=command.codigo_sku,
            stock=command.stock,
            categoria_id=command.categoria_id,
        )

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        operation_id = self.operation_service.create_operation(
            resource_type="item",
            event_type="item.created",
            resource_id=item.id,
        )

        event = DomainEvent(
            event_type="item.created",
            aggregate_type="item",
            aggregate_id=str(item.id),
            payload={
                **ItemRead.model_validate(item).model_dump(mode="json"),
                "categoria_nombre": categoria_nombre,
            },
            metadata={
                "source": "api-jmv",
                "user_id": self.current_user_id,
                "user_email": self.current_user_email,
                "operation_id": operation_id,
            },
        )
        publish_domain_event(event)

        logger.info("CQRS create item ok: id=%s operation_id=%s", item.id, operation_id)
        return CommandResult(resource_id=item.id, operation_id=operation_id)


class ActualizarItemHandler(CommandHandler[ActualizarItemCommand, CommandResult]):
    """
    Handler CQRS para actualizar items.
    """

    def __init__(self, db: Session, current_user_id: int | None = None, current_user_email: str | None = None):
        self.db = db
        self.current_user_id = current_user_id
        self.current_user_email = current_user_email
        self.operation_service = OperationService()

    def handle(self, command: ActualizarItemCommand) -> CommandResult:
        set_current_user_id(self.current_user_id)

        item = self.db.get(Item, command.item_id)
        if not item:
            raise ItemNoEncontradoError(command.item_id)

        categoria_nombre = None
        if command.categoria_id is not None:
            categoria = (
                self.db.execute(
                    select(Categoria).where(Categoria.id == command.categoria_id)
                )
                .scalars()
                .first()
            )
            if not categoria:
                raise ValueError(f"La categoría con id={command.categoria_id} no existe")
            categoria_nombre = categoria.nombre

        item.name = command.name
        item.description = command.description
        item.price = command.price
        item.sku = command.sku
        item.codigo_sku = command.codigo_sku
        item.stock = command.stock
        item.categoria_id = command.categoria_id

        self.db.commit()
        self.db.refresh(item)

        operation_id = self.operation_service.create_operation(
            resource_type="item",
            event_type="item.updated",
            resource_id=item.id,
        )

        event = DomainEvent(
            event_type="item.updated",
            aggregate_type="item",
            aggregate_id=str(item.id),
            payload={
                **ItemRead.model_validate(item).model_dump(mode="json"),
                "categoria_nombre": categoria_nombre,
            },
            metadata={
                "source": "api-jmv",
                "user_id": self.current_user_id,
                "user_email": self.current_user_email,
                "operation_id": operation_id,
            },
        )
        publish_domain_event(event)

        logger.info("CQRS update item ok: id=%s operation_id=%s", item.id, operation_id)
        return CommandResult(resource_id=item.id, operation_id=operation_id)


class EliminarItemHandler(CommandHandler[EliminarItemCommand, CommandResult]):
    """
    Handler CQRS para soft delete.
    """

    def __init__(self, db: Session, current_user_id: int | None = None, current_user_email: str | None = None):
        self.db = db
        self.current_user_id = current_user_id
        self.current_user_email = current_user_email
        self.operation_service = OperationService()

    def handle(self, command: EliminarItemCommand) -> CommandResult:
        set_current_user_id(self.current_user_id)

        item = self.db.get(Item, command.item_id)
        if not item:
            raise ItemNoEncontradoError(command.item_id)

        item.eliminado = True
        self.db.commit()
        self.db.refresh(item)

        operation_id = self.operation_service.create_operation(
            resource_type="item",
            event_type="item.deleted",
            resource_id=item.id,
        )

        event = DomainEvent(
            event_type="item.deleted",
            aggregate_type="item",
            aggregate_id=str(item.id),
            payload={
                **ItemRead.model_validate(item).model_dump(mode="json"),
                "categoria_nombre": None,
            },
            metadata={
                "source": "api-jmv",
                "user_id": self.current_user_id,
                "user_email": self.current_user_email,
                "operation_id": operation_id,
            },
        )
        publish_domain_event(event)

        logger.info("CQRS delete item ok: id=%s operation_id=%s", item.id, operation_id)
        return CommandResult(resource_id=item.id, operation_id=operation_id)