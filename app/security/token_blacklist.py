"""
Token Blacklisting y manejo de sesiones distribuidas.

Este módulo permite:
- Invalidar tokens JWT antes de su expiración natural
- Mantener sesiones activas en Redis
- Detectar uso sospechoso de tokens
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# -------------------------------------------------------------------
# Redis client
# -------------------------------------------------------------------

redis_client: Optional[redis.Redis] = None

try:
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception as e:
    logger.warning("Redis no disponible para token blacklist: %s", e)


# -------------------------------------------------------------------
# Blacklist
# -------------------------------------------------------------------


def blacklist_token(jti: str, expires_in: int) -> None:
    """
    Agrega un token al blacklist.

    jti: JWT ID único
    expires_in: segundos restantes de vida del token
    """
    if not redis_client:
        return

    key = f"blacklist:{jti}"

    try:
        redis_client.setex(key, expires_in, "revoked")
    except Exception as e:
        logger.error("Error agregando token al blacklist: %s", e)


def is_blacklisted(jti: str) -> bool:
    """
    Verifica si un token está revocado.
    """
    if not redis_client:
        return False

    key = f"blacklist:{jti}"

    try:
        return redis_client.exists(key) == 1
    except Exception:
        return False


# -------------------------------------------------------------------
# Sesiones distribuidas
# -------------------------------------------------------------------


def save_session(
    jti: str,
    user_id: int,
    ip: str,
    user_agent: str,
    expires_in: int,
) -> None:
    """
    Guarda metadata de sesión en Redis.
    """

    if not redis_client:
        return

    session_key = f"session:{jti}"
    user_sessions_key = f"user_sessions:{user_id}"

    payload = {
        "jti": jti,
        "user_id": user_id,
        "ip": ip,
        "user_agent": user_agent,
        "created_at": datetime.utcnow().isoformat(),
        "last_seen": datetime.utcnow().isoformat(),
    }

    try:
        redis_client.setex(session_key, expires_in, json.dumps(payload))
        redis_client.sadd(user_sessions_key, jti)
    except Exception as e:
        logger.error("Error guardando sesión: %s", e)


def update_last_seen(jti: str) -> None:
    """
    Actualiza el timestamp de actividad de la sesión.
    """

    if not redis_client:
        return

    key = f"session:{jti}"

    try:
        data = redis_client.get(key)

        if not data:
            return

        session = json.loads(data)
        session["last_seen"] = datetime.utcnow().isoformat()

        ttl = redis_client.ttl(key)

        redis_client.setex(key, ttl, json.dumps(session))

    except Exception:
        pass


def get_user_sessions(user_id: int) -> List[Dict[str, Any]]:
    """
    Devuelve sesiones activas de un usuario.
    """

    if not redis_client:
        return []

    user_sessions_key = f"user_sessions:{user_id}"

    try:
        jtis = redis_client.smembers(user_sessions_key)

        sessions: List[Dict[str, Any]] = []

        for jti in jtis:
            data = redis_client.get(f"session:{jti}")

            if data:
                sessions.append(json.loads(data))

        return sessions

    except Exception:
        return []


def close_session(jti: str) -> None:
    """
    Cierra una sesión específica.
    """

    if not redis_client:
        return

    session_key = f"session:{jti}"

    try:
        redis_client.delete(session_key)
        blacklist_token(jti, 3600)
    except Exception:
        pass


def revoke_all_user_tokens(user_id: int) -> None:
    """
    Revoca todos los tokens activos del usuario.
    """

    if not redis_client:
        return

    user_sessions_key = f"user_sessions:{user_id}"

    try:
        jtis = redis_client.smembers(user_sessions_key)

        for jti in jtis:
            blacklist_token(jti, 3600)

    except Exception:
        pass
