from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SKU_RETO_REGEX = re.compile(r"^[A-Z]{2}-\d{4}$")  # ej: AB-1234


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Nombre del item")
    description: Optional[str] = Field(None, max_length=500)
    price: float = Field(..., gt=0, description="Precio > 0")
    stock: int = Field(0, ge=0, description="Stock disponible (>=0)")

    # SKU legacy (sigue en tu modelo DB)
    sku: Optional[str] = Field(None, max_length=50, description="SKU libre (legacy)")

    # SKU del reto (AB-1234)
    codigo_sku: Optional[str] = Field(
        None,
        description="SKU opcional con formato AB-1234",
        examples=["AB-1234"],
    )

    @field_validator("name")
    @classmethod
    def name_title_case(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name no puede estar vacío")
        return v.title()

    @field_validator("price")
    @classmethod
    def price_max_two_decimals(cls, v: float) -> float:
        v = float(v)
        if round(v, 2) != v:
            raise ValueError("price no puede tener más de 2 decimales")
        return v

    @field_validator("codigo_sku")
    @classmethod
    def validate_codigo_sku(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().upper()
        if not SKU_RETO_REGEX.match(v):
            raise ValueError("codigo_sku inválido. Formato esperado: AB-1234")
        return v


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    price: float
    sku: Optional[str] = None
    codigo_sku: Optional[str] = None
    stock: int

    #--Soft delete fields
    eliminado: bool
    eliminado_en: Optional[datetime] = None

class ItemReadV2(ItemRead):
    precio_con_iva: float