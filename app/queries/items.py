from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ObtenerItemQuery:
    """
    Consulta un item por ID.
    """

    item_id: int


@dataclass
class ListarItemsQuery:
    """
    Lista paginada de items.
    """

    page: int = 1
    page_size: int = 10


@dataclass
class BuscarItemsQuery:
    """
    Búsqueda simple por término.
    """

    term: str
    page: int = 1
    page_size: int = 10
