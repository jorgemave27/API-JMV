from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from app.schemas.item import ItemCreate


class BulkCreate(BaseModel):
    items: List[ItemCreate] = Field(..., max_length=100)


class BulkDelete(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=100)


class BulkUpdateDisponible(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=100)
    disponible: bool
