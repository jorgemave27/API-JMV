"""
Servicio OAuth2 Authorization Code Flow.

Responsabilidades:

- generar authorization_code
- intercambiar code por tokens
- revocar refresh tokens
"""

import secrets
import uuid
from datetime import datetime, timedelta

import redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.oauth_refresh_token import OAuthRefreshToken
from app.models.usuario import Usuario

# conexión Redis existente en tu proyecto
redis_client = redis.Redis.from_url(settings.REDIS_URL)

# TTL del authorization code
AUTH_CODE_TTL = 600  # 10 minutos


def generate_authorization_code(user_email: str, client_id: str) -> str:
    """
    Genera authorization_code temporal.

    Se guarda en Redis con TTL de 10 minutos.
    """

    code = secrets.token_urlsafe(32)

    payload = f"{user_email}:{client_id}"

    redis_client.setex(
        f"oauth_code:{code}",
        AUTH_CODE_TTL,
        payload,
    )

    return code


def exchange_code_for_token(db: Session, code: str):
    """
    Intercambia authorization_code por:

    - access_token
    - refresh_token
    """

    key = f"oauth_code:{code}"

    data = redis_client.get(key)

    if not data:
        raise Exception("authorization_code inválido")

    # eliminar code para que sea de un solo uso
    redis_client.delete(key)

    user_email, client_id = data.decode().split(":")

    user = db.query(Usuario).filter(Usuario.email == user_email).first()

    if not user:
        raise Exception("Usuario no encontrado")

    # crear access token usando tu sistema actual
    access_token = create_access_token(user.email)

    # generar refresh token opaco
    refresh_token = str(uuid.uuid4())

    refresh = OAuthRefreshToken(
        token=refresh_token,
        user_email=user.email,
        client_id=client_id,
        expires_at=datetime.utcnow() + timedelta(days=30),
    )

    db.add(refresh)
    db.commit()

    return access_token, refresh_token


def revoke_refresh_token(db: Session, token: str):
    """
    Revoca refresh token.
    """

    obj = db.query(OAuthRefreshToken).filter(OAuthRefreshToken.token == token).first()

    if obj:
        obj.revoked = True
        db.commit()
