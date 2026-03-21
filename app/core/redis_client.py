"""
Redis Client HÍBRIDO (sync + async)

👉 Compatible con Chaos Engineering
👉 Fallback resiliente cuando Redis está "caído"
👉 Evita crashes en métricas, rate limit y cache
"""

from __future__ import annotations

import redis
import redis.asyncio as redis_async

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings

# ======================================================
# CHAOS STATE
# ======================================================
try:
    from app.api.v1.endpoints.chaos import CHAOS_STATE
except Exception:
    CHAOS_STATE = {
        "redis_down": False
    }


# ======================================================
# FAKE REDIS (CHAOS SAFE)
# ======================================================
class FakeRedis:
    """
    Simula Redis caído pero sin romper la app
    """

    async def get(self, *args, **kwargs):
        return None

    async def set(self, *args, **kwargs):
        return None

    async def delete(self, *args, **kwargs):
        return None

    async def exists(self, *args, **kwargs):
        return False

    async def incr(self, *args, **kwargs):
        return 1  # simula contador para métricas

    async def expire(self, *args, **kwargs):
        return True

    async def ttl(self, *args, **kwargs):
        return -1

    async def ping(self):
        return False

    async def close(self):
        return None


# ======================================================
# SYNC CLIENT (LEGACY)
# ======================================================
redis_client: Redis | None = None

if not CHAOS_STATE.get("redis_down"):
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )


# ======================================================
# ASYNC CLIENT (NEW)
# ======================================================
_async_client: AsyncRedis | None = None


async def get_redis_client() -> AsyncRedis | FakeRedis:
    """
    Devuelve cliente Redis real o FakeRedis en modo Chaos
    """

    global _async_client

    # 🔥 CHAOS: simular caída SIN romper sistema
    if CHAOS_STATE.get("redis_down"):
        return FakeRedis()

    if _async_client is None:
        _async_client = redis_async.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )

    return _async_client