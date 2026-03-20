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
import zlib
from typing import Any, Optional, Callable, Dict

from cachetools import TTLCache
from prometheus_client import Counter

# 🔥 USAMOS TU CLIENTE REAL
from app.core.redis_client import redis_client


# ==============================
# L1 CACHE (MEMORIA)
# ==============================
L1_CACHE = TTLCache(maxsize=1000, ttl=60)

# Locks por key (stampede protection)
_locks: Dict[str, asyncio.Lock] = {}


# ==============================
# SERIALIZACIÓN
# ==============================
def _serialize(value: Any) -> str:
    """
    Serializa y comprime si >1KB.
    Redis trabaja con strings (decode_responses=True)

    IMPORTANTE:
    - Si value no es JSON-serializable (ej. un modelo ORM),
      json.dumps lanzará TypeError.
    - Ese caso se controla en get_or_set para NO romper el flujo.
    """
    data = json.dumps(value)

    if len(data.encode()) > 1024:
        compressed = zlib.compress(data.encode())
        return "COMPRESSED:" + compressed.hex()

    return data


def _deserialize(value: str) -> Any:
    """
    Deserializa y descomprime si aplica
    """
    if value.startswith("COMPRESSED:"):
        hex_data = value.replace("COMPRESSED:", "", 1)
        decompressed = zlib.decompress(bytes.fromhex(hex_data))
        return json.loads(decompressed.decode())

    return json.loads(value)


def _get_lock(key: str) -> asyncio.Lock:
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    return _locks[key]


# ==============================
# MÉTRICAS
# ==============================
L1_HITS = Counter("cache_l1_hits", "L1 cache hits")
L2_HITS = Counter("cache_l2_hits", "L2 cache hits")
DB_HITS = Counter("cache_db_hits", "DB hits")


# ==============================
# CORE CACHE LOGIC
# ==============================
async def get_or_set(
    key: str,
    ttl: int,
    fetch_func: Callable,
    redis_ttl: Optional[int] = None,
) -> Any:
    """
    Flujo:
    L1 → L2 → DB

    IMPORTANTE:
    - Si el valor obtenido desde DB no es serializable JSON
      (por ejemplo, una entidad ORM como Item), NO se cachea,
      pero sí se devuelve sin romper el flujo.
    """

    # ---------- L1 ----------
    if key in L1_CACHE:
        L1_HITS.inc()
        return L1_CACHE[key]

    # ---------- L2 ----------
    cached = redis_client.get(key)
    if cached:
        value = _deserialize(cached)
        L2_HITS.inc()

        L1_CACHE[key] = value
        return value

    # ---------- STAMPEDE PROTECTION ----------
    lock = _get_lock(key)

    async with lock:
        # Double check L1
        if key in L1_CACHE:
            L1_HITS.inc()
            return L1_CACHE[key]

        # Double check L2
        cached = redis_client.get(key)
        if cached:
            value = _deserialize(cached)
            L2_HITS.inc()
            L1_CACHE[key] = value
            return value

        # ---------- DB ----------
        value = await fetch_func()
        DB_HITS.inc()

        if value is None:
            return None

        # =====================================================
        # Si el valor no es serializable (ej. modelo ORM),
        # NO rompemos el flujo: simplemente no lo cacheamos.
        # =====================================================
        try:
            serialized = _serialize(value)
        except TypeError:
            return value
        except Exception:
            return value

        # Guardar en L1
        try:
            L1_CACHE[key] = value
        except Exception:
            pass

        # Guardar en Redis
        try:
            redis_client.set(
                key,
                serialized,
                ex=redis_ttl or ttl,
            )
        except Exception:
            pass

        return value


# ==============================
# INVALIDACIÓN
# ==============================
async def invalidate(key: str):
    """
    Invalida L1 + L2
    """
    if key in L1_CACHE:
        del L1_CACHE[key]

    redis_client.delete(key)


async def invalidate_many(keys: list[str]):
    for key in keys:
        if key in L1_CACHE:
            del L1_CACHE[key]

    if keys:
        redis_client.delete(*keys)


# ==============================
# TAG BASED INVALIDATION
# ==============================
async def add_tag(tag: str, key: str):
    """
    Relaciona un key con un tag
    """
    redis_client.sadd(f"tag:{tag}", key)


async def invalidate_tag(tag: str):
    """
    Invalida todos los keys asociados a un tag
    """
    keys = redis_client.smembers(f"tag:{tag}")

    if keys:
        invalidate_keys = list(keys)
        await invalidate_many(invalidate_keys)

    redis_client.delete(f"tag:{tag}")