"""
Google OIDC SSO Integration.

- Authorization Code Flow
- Verificación correcta de ID Token (JWKS)
- JIT provisioning
- Group Sync
"""

from __future__ import annotations

import logging
from typing import Dict, Any

import httpx
from fastapi import HTTPException
from jose import jwt
from sqlalchemy.orm import Session

from google.oauth2 import id_token
from google.auth.transport import requests

from app.core.config import settings
from app.core.security import create_access_token
from app.models.usuario import Usuario

logger = logging.getLogger(__name__)


# =====================================================
# DISCOVERY
# =====================================================

async def get_google_provider_cfg() -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(settings.GOOGLE_DISCOVERY_URL)
        res.raise_for_status()
        return res.json()


# =====================================================
# TOKEN EXCHANGE
# =====================================================

async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    config = await get_google_provider_cfg()
    token_endpoint = config["token_endpoint"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            token_endpoint,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Error intercambiando code: {response.text}",
        )

    return response.json()


# =====================================================
# VERIFY ID TOKEN (🔥 FIX REAL)
# =====================================================

async def verify_id_token(id_token_str: str) -> Dict[str, Any]:
    """
    Verificación oficial de Google (NO falla)
    """

    try:
        request = requests.Request()

        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            request,
            settings.GOOGLE_CLIENT_ID,
        )

        return idinfo

    except Exception as e:
        logger.error("Google ID Token inválido: %s", e)
        raise HTTPException(status_code=401, detail="ID Token inválido")

# =====================================================
# JIT PROVISIONING + GROUP SYNC
# =====================================================

def sync_user_from_google(
    db: Session,
    claims: Dict[str, Any],
) -> Usuario:

    email = claims.get("email")
    name = claims.get("name")

    if not email:
        raise HTTPException(status_code=400, detail="Email no presente")

    user = db.query(Usuario).filter(Usuario.email == email).first()

    # ROLE DEFAULT
    mapped_role = "lector"

    # SIMPLE GROUP SYNC POR EMAIL
    for group, role in settings.SSO_GROUP_ROLE_MAPPING.items():
        if email == group:
            mapped_role = role

    if not user:
        user = Usuario(
            nombre=name,
            email=email,
            hashed_password="SSO_USER",
            rol=mapped_role,
            activo=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.rol = mapped_role
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


# =====================================================
# MAIN FLOW
# =====================================================

async def handle_google_callback(db: Session, code: str) -> str:

    tokens = await exchange_code_for_tokens(code)

    id_token = tokens.get("id_token")

    if not id_token:
        raise HTTPException(status_code=400, detail="No ID token")

    claims = await verify_id_token(id_token)

    user = sync_user_from_google(db, claims)

    access_token = create_access_token(user.email)

    return access_token