from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str
    type: str
    exp: int


class UsuarioAuthRead(BaseModel):
    id: int
    email: EmailStr
    activo: bool
    rol: str

    model_config = {"from_attributes": True}