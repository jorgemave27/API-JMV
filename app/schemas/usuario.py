from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import validate_password_complexity


class UsuarioCreate(BaseModel):
    """
    Schema para registro de usuarios.
    """

    email: EmailStr
    password: str = Field(..., min_length=8)
    rol: str = Field(default="lector")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        validate_password_complexity(value)
        return value

    @field_validator("rol")
    @classmethod
    def validate_rol(cls, value: str) -> str:
        allowed = {"admin", "editor", "lector"}
        if value not in allowed:
            raise ValueError("rol inválido. Debe ser admin, editor o lector")
        return value


class UsuarioRead(BaseModel):
    """
    Schema de salida segura para usuarios.
    Nunca expone hashed_password.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    activo: bool
    rol: str
    failed_login_attempts: int
    blocked_until: Optional[datetime] = None
    created_at: datetime