"""
Endpoints OAuth2 Authorization Code Flow + Google SSO (OIDC).
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.database.database import get_db
from app.models.usuario import Usuario
from app.oauth.service import (
    exchange_code_for_token,
    generate_authorization_code,
    revoke_refresh_token,
)

#SSO GOOGLE
from app.oauth.google_sso import handle_google_callback


# =====================================================
# ROUTER
# =====================================================

router = APIRouter(prefix="/oauth", tags=["OAuth2 / SSO"])


# =====================================================
# OAUTH2 STANDARD FLOW
# =====================================================

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


# =====================================================
# GOOGLE SSO (OIDC)
# =====================================================

@router.get("/google")
async def google_login():
    """
    🔐 Redirige al usuario a Google para autenticación SSO.
    """

    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&access_type=offline"
        f"&prompt=consent"
    )

    return RedirectResponse(google_auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    db: Session = Depends(get_db),
):
    """
     Callback de Google.

    Flujo:
    1. Recibe authorization code
    2. Intercambia por ID Token
    3. Verifica token (JWKS)
    4. JIT provisioning (crea usuario si no existe)
    5. Aplica Group Sync → rol
    6. Genera JWT propio de la API
    """

    access_token = await handle_google_callback(db, code)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }