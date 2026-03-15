"""
Redis Client centralizado.

Se utiliza para:
- Cache
- Anomaly Detection
- Rate limiting
- Geo cache
- Seguridad

La conexión se obtiene desde REDIS_URL configurado
en settings o variables de entorno.
"""

from __future__ import annotations

import redis
from redis import Redis

from app.core.config import settings


def get_redis_client() -> Redis:
    """
    Retorna cliente Redis reutilizable para toda la app.

    decode_responses=True permite trabajar con strings
    en lugar de bytes.
    """
    return redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )


# cliente global reutilizable
redis_client: Redis = get_redis_client()
