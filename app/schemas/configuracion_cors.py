from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ConfiguracionCorsCreate(BaseModel):
    origin: str = Field(..., min_length=1, max_length=255)

    @field_validator("origin")
    @classmethod
    def validar_origin(cls, value: str) -> str:
        value = value.strip()
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("El origin debe iniciar con http:// o https://")
        return value


class ConfiguracionCorsRead(BaseModel):
    id: int
    origin: str
    activo: bool
    creado_en: datetime

    model_config = {"from_attributes": True}