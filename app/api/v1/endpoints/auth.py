from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.database.database import get_db
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, RefreshTokenRequest, TokenResponse

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login de usuario con JWT",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Autentica un usuario por email y password y retorna access/refresh tokens.
    """
    user = db.query(Usuario).filter(Usuario.email == payload.email).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo",
        )

    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    return TokenResponse(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),
        token_type="bearer",
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token con refresh token",
)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Recibe un refresh_token válido y devuelve un nuevo access_token.
    """
    token_payload = decode_token(payload.refresh_token)

    token_type = token_payload.get("type")
    subject = token_payload.get("sub")

    if token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un refresh token válido",
        )

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: subject ausente",
        )

    user = db.query(Usuario).filter(Usuario.email == subject).first()

    if user is None or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no válido para refrescar token",
        )

    return TokenResponse(
        access_token=create_access_token(user.email),
        refresh_token=payload.refresh_token,
        token_type="bearer",
    )