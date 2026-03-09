from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.sanitizers import sanitize_text
from app.schemas.categoria import CategoriaResponse

SKU_RETO_REGEX = re.compile(r"^[A-Z]{2}-\d{4}$")  # ej: AB-1234


class ItemCreate(BaseModel):
    """
    Schema de entrada para crear un item.

    Incluye validaciones de:
    - nombre
    - descripción
    - precio
    - codigo_sku
    - stock
    - categoria_id opcional

    Sanitización aplicada:
    - name
    - description
    """

    name: str = Field(..., min_length=1, max_length=200, description="Nombre del item")
    description: Optional[str] = Field(None, max_length=500)
    price: float = Field(..., gt=0, description="Precio > 0")
    stock: int = Field(0, ge=0, description="Stock disponible (>=0)")

    sku: Optional[str] = Field(None, max_length=50, description="SKU libre (legacy)")

    codigo_sku: Optional[str] = Field(
        None,
        description="SKU opcional con formato AB-1234",
        examples=["AB-1234"],
    )

    categoria_id: Optional[int] = Field(
        None,
        ge=1,
        description="ID de la categoría asociada",
    )

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return sanitize_text(v, field_name="name", max_length=200).title()

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return sanitize_text(v, field_name="description", max_length=500)

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
    """
    Schema de salida para items.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    price: float
    sku: Optional[str] = None
    codigo_sku: Optional[str] = None
    stock: int
    categoria_id: Optional[int] = None
    categoria: Optional[CategoriaResponse] = None
    eliminado: bool
    eliminado_en: Optional[datetime] = None


class ItemReadV2(ItemRead):
    """
    Schema de salida para items en v2.
    """

    precio_con_iva: float