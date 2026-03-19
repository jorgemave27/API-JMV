from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.security import validate_password_complexity


class UsuarioCreate(BaseModel):
    """
    Schema para registro de usuarios.
    """

    nombre: Optional[str] = Field(default=None, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)
    rol: str = Field(default="lector")
    rfc: Optional[str] = Field(default=None, max_length=255)

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

    @field_validator("nombre")
    @classmethod
    def validate_nombre(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        value = value.strip()
        if not value:
            return None

        return value

    @field_validator("rfc")
    @classmethod
    def validate_rfc(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        value = value.strip().upper()
        if not value:
            return None

        return value


class UsuarioRead(BaseModel):
    """
    Schema de salida segura para usuarios.
    Nunca expone hashed_password.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: Optional[str] = None
    email: EmailStr
    activo: bool
    rol: str
    failed_login_attempts: int
    blocked_until: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    ultimo_acceso_at: Optional[datetime] = None


class UsuarioDatosPersonalesRead(BaseModel):
    """
    Schema para derecho de ACCESO.
    Expone todos los datos personales relevantes del usuario.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: Optional[str] = None
    email: EmailStr
    rfc: Optional[str] = None
    activo: bool
    rol: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    ultimo_acceso_at: Optional[datetime] = None
    ip_cliente_actual: Optional[str] = None


class UsuarioRectificarRequest(BaseModel):
    """
    Schema para derecho de RECTIFICACIÓN.
    Permite corregir datos personales.
    """

    nombre: Optional[str] = Field(default=None, max_length=255)
    email: Optional[EmailStr] = None
    rfc: Optional[str] = Field(default=None, max_length=255)

    @field_validator("nombre")
    @classmethod
    def validate_nombre(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        value = value.strip()
        if not value:
            return None

        return value

    @field_validator("rfc")
    @classmethod
    def validate_rfc(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        value = value.strip().upper()
        if not value:
            return None

        return value

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "UsuarioRectificarRequest":
        if self.nombre is None and self.email is None and self.rfc is None:
            raise ValueError("Debes enviar al menos un campo para rectificar")
        return self
