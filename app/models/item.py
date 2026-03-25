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


# =====================================================
# HELPERS SERIALIZACIÓN
# =====================================================

def _serialize_value(value: Any) -> Any:
    """
    Convierte valores no serializables a JSON seguro.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _serialize_item_state(target: "Item") -> dict[str, Any]:
    """
    Serializa TODO el estado actual del item.
    """
    return {
        column.name: _serialize_value(getattr(target, column.name))
        for column in target.__table__.columns
    }


def _build_previous_and_new_state(target: "Item") -> tuple[dict[str, Any], dict[str, Any], bool]:
    """
    Construye snapshot anterior vs nuevo.
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
    Inserta auditoría en la misma transacción.
    """

    try:
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
    except Exception:
        # 🔥 IMPORTANTE:
        # nunca romper la operación principal por auditoría
        pass


# =====================================================
# MODELO ITEM
# =====================================================

class Item(Base):
    """
    Modelo principal de Item.

    🔥 Incluye integración con S3:
    - imagen_key = referencia interna al archivo
    """

    __tablename__ = "items"

    __table_args__ = (
        Index("ix_items_name_eliminado", "name", "eliminado"),
    )

    # -----------------------------
    # ID
    # -----------------------------
    id = Column(Integer, primary_key=True, index=True)

    # -----------------------------
    # DATOS
    # -----------------------------
    name = Column(String(200), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    price = Column(Float, nullable=False)

    sku = Column(String(50), nullable=True, unique=True, index=True)
    codigo_sku = Column(String(20), nullable=True, index=True)

    stock = Column(Integer, nullable=False, default=0)
    proveedor = Column(String(255), nullable=True)

    # -----------------------------
    # 🔥 S3
    # -----------------------------
    imagen_key = Column(
        String(255),
        nullable=True,
        comment="Clave del archivo en S3 (NO URL)",
    )

    # -----------------------------
    # RELACIONES
    # -----------------------------
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    categoria = relationship("Categoria", back_populates="items")

    # -----------------------------
    # SOFT DELETE
    # -----------------------------
    eliminado = Column(Boolean, nullable=False, default=False, index=True)
    eliminado_en = Column(DateTime, nullable=True)

    # -----------------------------
    # TIMESTAMPS
    # -----------------------------
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )


# =====================================================
# EVENTOS DE AUDITORÍA
# =====================================================

@event.listens_for(Item, "after_insert")
def audit_item_after_insert(mapper, connection, target: Item) -> None:
    _insert_audit_row(
        connection,
        item_id=target.id,
        accion="CREATE",
        datos_anteriores=None,
        datos_nuevos=_serialize_item_state(target),
    )


@event.listens_for(Item, "after_update")
def audit_item_after_update(mapper, connection, target: Item) -> None:
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
    _insert_audit_row(
        connection,
        item_id=target.id,
        accion="DELETE",
        datos_anteriores=_serialize_item_state(target),
        datos_nuevos=None,
    )