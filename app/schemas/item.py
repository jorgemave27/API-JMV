from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


SKU_REGEX = re.compile(r"^[A-Z0-9-]{4,20}$")


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Nombre del item")
    description: Optional[str] = Field(None, max_length=500)
    price: float = Field(..., gt=0, description="Precio > 0")
    sku: Optional[str] = Field(None, description="SKU (A-Z, 0-9, -)")

    @field_validator("name")
    @classmethod
    def name_title_case(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name no puede estar vacío")
        # Title Case simple
        return v.title()

    @field_validator("price")
    @classmethod
    def price_two_decimals(cls, v: float) -> float:
        return round(float(v), 2)

    @field_validator("sku")
    @classmethod
    def sku_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if not SKU_REGEX.match(v):
            raise ValueError("sku inválido. Usa A-Z, 0-9 y '-' (4 a 20 chars)")
        return v


class ItemRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    sku: Optional[str] = None

    class Config:
        from_attributes = True


