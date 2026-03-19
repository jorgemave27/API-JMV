"""
Endpoints OAuth2 Authorization Code Flow.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.database import get_db
from app.models.usuario import Usuario
from app.oauth.service import (
    exchange_code_for_token,
    generate_authorization_code,
    revoke_refresh_token,
)

router = APIRouter(prefix="/oauth", tags=["OAuth2"])


@router.get("/authorize")
def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str,
    scope: str,
    current_user: Usuario = Depends(get_current_user),
):
    """
    Endpoint de autorización OAuth2.

    El usuario ya debe estar autenticado.
    """

    if response_type != "code":
        raise HTTPException(status_code=400, detail="response_type inválido")

    code = generate_authorization_code(
        current_user.email,
        client_id,
    )

    return {
        "authorization_code": code,
        "expires_in": 600,
    }


@router.post("/token")
def token(
    code: str,
    db: Session = Depends(get_db),
):
    """
    Intercambio authorization_code por tokens.
    """

    access_token, refresh_token = exchange_code_for_token(db, code)

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 900,
        "refresh_token": refresh_token,
    }


@router.post("/revoke")
def revoke(
    refresh_token: str,
    db: Session = Depends(get_db),
):
    """
    Revoca refresh token.
    """

    revoke_refresh_token(db, refresh_token)

    return {"status": "revoked"}


@router.get("/userinfo")
def userinfo(current_user: Usuario = Depends(get_current_user)):
    """
    Endpoint estándar OAuth2.

    Devuelve información del usuario.
    """

    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.rol,
    }
