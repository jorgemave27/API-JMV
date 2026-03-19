"""
Gestión centralizada de API Keys con soporte para rotación.

Responsabilidades:
- Leer API key activa desde Vault o settings
- Mantener una ventana de convivencia con la key anterior
- Guardar keys en Redis para tolerar requests en vuelo
- NO romper tests/local si Redis no está disponible
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

import redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.vault import vault_client

REDIS_API_KEY_ACTIVE = "security:api_key:active"
REDIS_API_KEY_PREVIOUS = "security:api_key:previous"
REDIS_API_KEY_ROTATED_AT = "security:api_key:rotated_at"

# Ventana de convivencia para no romper requests en vuelo
PREVIOUS_KEY_TTL_SECONDS = 300  # 5 minutos


class ApiKeyManager:
    """
    Administrador de API Keys.

    Importante:
    - Si Redis no está disponible, hace fallback a memoria/settings
    - Esto evita romper tests locales o builds Docker
    """

    def __init__(self) -> None:
        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )

        # Fallback local en memoria
        self._active_key_fallback = settings.API_KEY
        self._previous_key_fallback: str | None = None

    def _redis_get(self, key: str) -> str | None:
        """
        Lee una clave de Redis con tolerancia a fallos.
        """
        try:
            return self.redis_client.get(key)
        except RedisError:
            return None
        except OSError:
            return None

    def _redis_set(self, key: str, value: str) -> None:
        """
        Guarda una clave en Redis con tolerancia a fallos.
        """
        try:
            self.redis_client.set(key, value)
        except RedisError:
            pass
        except OSError:
            pass

    def _redis_setex(self, key: str, ttl_seconds: int, value: str) -> None:
        """
        Guarda una clave con expiración en Redis con tolerancia a fallos.
        """
        try:
            self.redis_client.setex(key, ttl_seconds, value)
        except RedisError:
            pass
        except OSError:
            pass

    def get_active_api_key(self) -> str:
        """
        Obtiene la API key activa.

        Prioridad:
        1. Redis
        2. Vault
        3. Fallback en memoria/settings
        """
        redis_value = self._redis_get(REDIS_API_KEY_ACTIVE)

        if redis_value:
            self._active_key_fallback = redis_value
            return redis_value

        if vault_client.enabled():
            try:
                secrets_data = vault_client.read_secret("secret/mi-api")
                vault_api_key = secrets_data.get("API_KEY")

                if vault_api_key:
                    self._active_key_fallback = vault_api_key
                    self._redis_set(REDIS_API_KEY_ACTIVE, vault_api_key)
                    return vault_api_key
            except Exception:
                pass

        return self._active_key_fallback

    def get_previous_api_key(self) -> str | None:
        """
        Obtiene la API key anterior si existe todavía
        dentro de la ventana de convivencia.
        """
        redis_value = self._redis_get(REDIS_API_KEY_PREVIOUS)

        if redis_value:
            self._previous_key_fallback = redis_value
            return redis_value

        return self._previous_key_fallback

    def is_valid_api_key(self, candidate: str | None) -> bool:
        """
        Valida una API key contra la activa y la anterior.
        """
        if not candidate:
            return False

        active_key = self.get_active_api_key()
        previous_key = self.get_previous_api_key()

        return candidate == active_key or candidate == previous_key

    def rotate_api_key(self) -> str:
        """
        Rota la API key:
        - genera una nueva
        - mueve la actual a previous
        - persiste la nueva en Vault
        - persiste ambas en Redis
        - mantiene fallback en memoria si Redis no está disponible
        """
        current_key = self.get_active_api_key()
        new_key = secrets.token_urlsafe(32)

        # Fallback local
        self._previous_key_fallback = current_key
        self._active_key_fallback = new_key

        # Guardar anterior por ventana corta
        self._redis_setex(
            REDIS_API_KEY_PREVIOUS,
            PREVIOUS_KEY_TTL_SECONDS,
            current_key,
        )

        # Guardar nueva activa
        self._redis_set(REDIS_API_KEY_ACTIVE, new_key)
        self._redis_set(
            REDIS_API_KEY_ROTATED_AT,
            datetime.now(timezone.utc).isoformat(),
        )

        # Persistir en Vault si está disponible
        if vault_client.enabled():
            try:
                secrets_data = vault_client.read_secret("secret/mi-api")
            except Exception:
                secrets_data = {}

            secrets_data["API_KEY"] = new_key

            try:
                vault_client.write_secret("secret/mi-api", secrets_data)
            except Exception:
                pass

        return new_key


api_key_manager = ApiKeyManager()
