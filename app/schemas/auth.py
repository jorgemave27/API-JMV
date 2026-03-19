from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import validate_password_complexity


class LoginRequest(BaseModel):
    """
    Schema para login.
    """

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """
    Respuesta estándar de tokens JWT.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """
    Schema para refrescar access token.
    """

    refresh_token: str


class TokenPayload(BaseModel):
    """
    Payload decodificado del JWT.
    """

    sub: str
    type: str
    exp: int


class UsuarioAuthRead(BaseModel):
    """
    Lectura segura de usuario autenticado.
    """

    id: int
    email: EmailStr
    activo: bool
    rol: str

    model_config = {"from_attributes": True}


class CambiarPasswordRequest(BaseModel):
    """
    Schema para cambio de contraseña autenticado.
    """

    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        validate_password_complexity(value)
        return value


class ForgotPasswordRequest(BaseModel):
    """
    Schema para solicitar recuperación de contraseña.
    """

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """
    Schema para restablecer contraseña con token.
    """

    token: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        validate_password_complexity(value)
        return value
