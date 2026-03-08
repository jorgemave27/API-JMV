from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    event,
    insert,
    inspect,
)
from sqlalchemy.orm import relationship

from app.core.request_context import get_current_client_ip, get_current_user_id
from app.database.database import Base
from app.models.auditoria_item import AuditoriaItem


# -------------------------------------------------------------------
# Helpers internos para serialización
# -------------------------------------------------------------------

def _serialize_value(value: Any) -> Any:
    """
    Convierte valores no serializables directamente a JSON
    a formatos seguros.

    Ejemplo:
    - datetime -> ISO string
    - date -> ISO string
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _serialize_item_state(target: "Item") -> dict[str, Any]:
    """
    Convierte el estado completo actual del item a dict serializable.
    """
    return {
        column.name: _serialize_value(getattr(target, column.name))
        for column in target.__table__.columns
    }


def _build_previous_and_new_state(target: "Item") -> tuple[dict[str, Any], dict[str, Any], bool]:
    """
    Construye snapshot anterior y nuevo del item para auditoría.

    Returns:
        tuple:
            - previous: estado anterior
            - new_state: estado nuevo
            - has_changes: indica si hubo cambios reales
    """
    state = inspect(target)

    previous: dict[str, Any] = {}
    new_state: dict[str, Any] = {}
    has_changes = False

    for column in target.__table__.columns:
        attr_state = state.attrs[column.name]
        history = attr_state.history
        current_value = getattr(target, column.name)

        if history.has_changes():
            has_changes = True
            old_value = history.deleted[0] if history.deleted else None
        else:
            old_value = current_value

        previous[column.name] = _serialize_value(old_value)
        new_state[column.name] = _serialize_value(current_value)

    return previous, new_state, has_changes


def _insert_audit_row(
    connection,
    *,
    item_id: int,
    accion: str,
    datos_anteriores: dict[str, Any] | None,
    datos_nuevos: dict[str, Any] | None,
) -> None:
    """
    Inserta un registro en auditoria_items usando la misma conexión
    de la transacción actual.

    Esto garantiza que la auditoría viaje junto con el cambio real.
    """
    connection.execute(
        insert(AuditoriaItem).values(
            item_id=item_id,
            accion=accion,
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_nuevos,
            usuario_id=get_current_user_id(),
            ip_cliente=get_current_client_ip(),
            timestamp=datetime.utcnow(),
        )
    )


class Item(Base):
    """
    Modelo de Item dentro del sistema.

    Representa un producto o elemento gestionado por la API.

    Campos principales:
    - id: identificador único
    - name: nombre del item
    - description: descripción opcional
    - price: precio del item
    - sku: SKU legacy del sistema
    - codigo_sku: SKU con formato validado (AB-1234)
    - stock: cantidad disponible en inventario

    Soft delete:
    - eliminado: indica si el item fue eliminado lógicamente
    - eliminado_en: fecha en que se eliminó

    Relaciones:
    - categoria_id: clave foránea hacia la tabla categorias
    - categoria: relación ORM hacia el modelo Categoria
    """

    __tablename__ = "items"

    # -------------------------------------------------------------
    # Índice compuesto para búsquedas frecuentes
    # -------------------------------------------------------------
    __table_args__ = (
        Index("ix_items_name_eliminado", "name", "eliminado"),
    )

    # -------------------------------------------------------------
    # Identificación básica
    # -------------------------------------------------------------
    id = Column(Integer, primary_key=True, index=True)

    # -------------------------------------------------------------
    # Información del item
    # -------------------------------------------------------------
    name = Column(String(200), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    price = Column(Float, nullable=False)

    # SKU legacy del sistema
    sku = Column(String(50), nullable=True, unique=True, index=True)

    # SKU validado (AB-1234)
    codigo_sku = Column(String(20), nullable=True, index=True)

    stock = Column(Integer, nullable=False, default=0)
    proveedor = Column(String(255), nullable=True)

    # -------------------------------------------------------------
    # Relación con Categoría
    # -------------------------------------------------------------
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    categoria = relationship("Categoria", back_populates="items")

    # -------------------------------------------------------------
    # Soft delete
    # -------------------------------------------------------------
    eliminado = Column(Boolean, nullable=False, default=False, index=True)
    eliminado_en = Column(DateTime, nullable=True)

    # -------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )


# -------------------------------------------------------------------
# Eventos ORM de auditoría
# -------------------------------------------------------------------

@event.listens_for(Item, "after_insert")
def audit_item_after_insert(mapper, connection, target: Item) -> None:
    """
    Registra auditoría después de crear un item.
    """
    _insert_audit_row(
        connection,
        item_id=target.id,
        accion="CREATE",
        datos_anteriores=None,
        datos_nuevos=_serialize_item_state(target),
    )


@event.listens_for(Item, "after_update")
def audit_item_after_update(mapper, connection, target: Item) -> None:
    """
    Registra auditoría después de actualizar un item.

    Regla especial:
    - si eliminado pasa de False a True, se registra como DELETE lógico
    - en otro caso, se registra como UPDATE
    """
    previous, new_state, has_changes = _build_previous_and_new_state(target)

    if not has_changes:
        return

    accion = (
        "DELETE"
        if previous.get("eliminado") is False and new_state.get("eliminado") is True
        else "UPDATE"
    )

    _insert_audit_row(
        connection,
        item_id=target.id,
        accion=accion,
        datos_anteriores=previous,
        datos_nuevos=new_state,
    )


@event.listens_for(Item, "after_delete")
def audit_item_after_delete(mapper, connection, target: Item) -> None:
    """
    Registra auditoría después de eliminar físicamente un item.
    """
    _insert_audit_row(
        connection,
        item_id=target.id,
        accion="DELETE",
        datos_anteriores=_serialize_item_state(target),
        datos_nuevos=None,
    )