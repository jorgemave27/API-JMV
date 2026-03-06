from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.item import ItemRead


class CursorPaginationResponse(BaseModel):
    """
    Respuesta de paginación por cursor.

    - items: elementos de la página actual
    - next_cursor: id del último item retornado, o None si ya no hay más
    - has_more: indica si existe una siguiente página
    """

    items: list[ItemRead] = Field(default_factory=list)
    next_cursor: int | None = None
    has_more: bool