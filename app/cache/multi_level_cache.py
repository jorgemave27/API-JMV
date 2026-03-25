"""
MULTI LEVEL CACHE SYSTEM (L1 + L2 + DB)

- L1: memoria local (cachetools)
- L2: Redis (sync client)
- L3: Base de datos
- Protección contra cache stampede
- Compresión automática >1KB
- Tag-based invalidation
"""

from __future__ import annotations

import asyncio
import json
import os
import zlib
from typing import Any, Optional, Callable, Dict

from cachetools import TTLCache
from prometheus_client import Counter

# 🔥 USAMOS TU CLIENTE REAL
from app.core.redis_client import redis_client


# ==========================================================
# TEST MODE (DESACTIVA CACHE/REDIS)
# ==========================================================
TESTING = os.getenv("TESTING", "false").lower() == "true"


# ==========================================================
# L1 CACHE (MEMORIA)
# ==========================================================
L1_CACHE = TTLCache(maxsize=1000, ttl=60)

# Locks por key (stampede protection)
_locks: Dict[str, asyncio.Lock] = {}


# ==========================================================
# SERIALIZACIÓN
# ==========================================================
def _serialize(value: Any) -> str:
    data = json.dumps(value)

    if len(data.encode()) > 1024:
        compressed = zlib.compress(data.encode())
        return "COMPRESSED:" + compressed.hex()

    return data


def _deserialize(value: str) -> Any:
    if value.startswith("COMPRESSED:"):
        hex_data = value.replace("COMPRESSED:", "", 1)
        decompressed = zlib.decompress(bytes.fromhex(hex_data))
        return json.loads(decompressed.decode())

    return json.loads(value)


def _get_lock(key: str) -> asyncio.Lock:
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


# ==========================================================
# MÉTRICAS
# ==========================================================
L1_HITS = Counter("cache_l1_hits", "L1 cache hits")
L2_HITS = Counter("cache_l2_hits", "L2 cache hits")
DB_HITS = Counter("cache_db_hits", "DB hits")


# ==========================================================
# CORE CACHE LOGIC
# ==========================================================
async def get_or_set(
    key: str,
    ttl: int,
    fetch_func: Callable,
    redis_ttl: Optional[int] = None,
) -> Any:
    """
    Flujo:
    L1 → L2 → DB
    """

    # 🔥 EN TEST: SIN CACHE
    if TESTING:
        return await fetch_func()

    # ---------- L1 ----------
    if key in L1_CACHE:
        L1_HITS.inc()
        return L1_CACHE[key]

    # ---------- L2 ----------
    try:
        cached = redis_client.get(key)
    except Exception:
        cached = None

    if cached:
        value = _deserialize(cached)
        L2_HITS.inc()
        L1_CACHE[key] = value
        return value

    # ---------- LOCK ----------
    lock = _get_lock(key)

    async with lock:
        if key in L1_CACHE:
            return L1_CACHE[key]

        try:
            cached = redis_client.get(key)
        except Exception:
            cached = None

        if cached:
            value = _deserialize(cached)
            L1_CACHE[key] = value
            return value

        # ---------- DB ----------
        value = await fetch_func()
        DB_HITS.inc()

        if value is None:
            return None

        try:
            serialized = _serialize(value)
        except Exception:
            return value

        try:
            L1_CACHE[key] = value
        except Exception:
            pass

        try:
            redis_client.set(key, serialized, ex=redis_ttl or ttl)
        except Exception:
            pass

        return value


# ==========================================================
# INVALIDACIÓN
# ==========================================================
async def invalidate(key: str):
    if key in L1_CACHE:
        del L1_CACHE[key]

    if TESTING:
        return

    try:
        redis_client.delete(key)
    except Exception:
        pass


async def invalidate_many(keys: list[str]):
    for key in keys:
        if key in L1_CACHE:
            del L1_CACHE[key]

    if TESTING:
        return

    try:
        redis_client.delete(*keys)
    except Exception:
        pass


# ==========================================================
# TAG BASED INVALIDATION
# ==========================================================
async def add_tag(tag: str, key: str):
    if TESTING:
        return

    try:
        redis_client.sadd(f"tag:{tag}", key)
    except Exception:
        pass


async def invalidate_tag(tag: str):
    if TESTING:
        return

    try:
        keys = redis_client.smembers(f"tag:{tag}")

        if keys:
            await invalidate_many(list(keys))

        redis_client.delete(f"tag:{tag}")
    except Exception:
        pass