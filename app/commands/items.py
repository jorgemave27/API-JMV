from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CrearItemCommand:
    """
    Comando para crear un item.
    """

    name: str
    description: str | None
    price: float
    sku: str | None
    codigo_sku: str | None
    stock: int
    categoria_id: int | None = None


@dataclass
class ActualizarItemCommand:
    """
    Comando para actualizar un item.
    """

    item_id: int
    name: str
    description: str | None
    price: float
    sku: str | None
    codigo_sku: str | None
    stock: int
    categoria_id: int | None = None


@dataclass
class EliminarItemCommand:
    """
    Comando para soft delete de un item.
    """

    item_id: int
