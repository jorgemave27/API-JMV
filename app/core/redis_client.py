"""
Redis Client HÍBRIDO (sync + async)

👉 Mantiene compatibilidad con código viejo
👉 Permite usar async para nuevas partes
"""

from __future__ import annotations

import redis
import redis.asyncio as redis_async

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings

# ======================================================
# SYNC CLIENT (LEGACY)
# ======================================================
redis_client: Redis = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)

# ======================================================
# ASYNC CLIENT (NEW)
# ======================================================
_async_client: AsyncRedis | None = None


async def get_redis_client() -> AsyncRedis:
    global _async_client

    if _async_client is None:
        _async_client = redis_async.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )

    return _async_client