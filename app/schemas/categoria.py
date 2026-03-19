from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoriaBase(BaseModel):
    """
    Schema base para categorías.

    Se reutiliza para creación, actualización y lectura.
    """

    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre único de la categoría")
    descripcion: Optional[str] = Field(None, max_length=255, description="Descripción opcional")

    @field_validator("nombre")
    @classmethod
    def nombre_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nombre no puede estar vacío")
        return v.title()


class CategoriaCreate(CategoriaBase):
    """
    Schema para crear una categoría.
    """

    pass


class CategoriaUpdate(BaseModel):
    """
    Schema para actualizar una categoría.

    Todos los campos son opcionales para permitir updates parciales.
    """

    nombre: Optional[str] = Field(None, min_length=1, max_length=100)
    descripcion: Optional[str] = Field(None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def nombre_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("nombre no puede estar vacío")
        return v.title()


class CategoriaResponse(BaseModel):
    """
    Schema de salida para categorías.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    descripcion: Optional[str] = None
    creado_en: datetime
