from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pybreaker

from app.core.cache import get_cache, set_cache
from app.core.config import settings
from app.resilience.circuit_breaker import execute_with_breaker

logger = logging.getLogger(__name__)


def _cache_key(service_name: str, cache_key: str) -> str:
    return f"api-jmv:external:{service_name}:{cache_key}"


def _http_get_json(url: str, timeout: float) -> dict[str, Any]:
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def get_external_data_with_resilience(
    *,
    service_name: str,
    breaker_name: str,
    url: str,
    cache_key: str,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    redis_key = _cache_key(service_name, cache_key)

    try:
        payload = execute_with_breaker(
            breaker_name,
            _http_get_json,
            url,
            settings.EXTERNAL_HTTP_TIMEOUT_SECONDS,
        )

        cached_payload = {
            "source": service_name,
            "stale": False,
            "data": payload,
        }
        set_cache(redis_key, cached_payload, ttl_seconds)

        return cached_payload

    except pybreaker.CircuitBreakerError:
        logger.warning(
            "Circuit breaker abierto para service_name=%s breaker_name=%s",
            service_name,
            breaker_name,
        )

        cached = get_cache(redis_key)
        if cached is not None:
            cached["stale"] = True
            return cached

        return {
            "source": service_name,
            "stale": True,
            "data": None,
            "message": "Circuit breaker abierto y sin datos cacheados",
        }

    except Exception as exc:
        logger.error(
            "Error consumiendo servicio externo service_name=%s error=%s",
            service_name,
            repr(exc),
        )

        cached = get_cache(redis_key)
        if cached is not None:
            cached["stale"] = True
            cached["message"] = "Respuesta cacheada por fallo del servicio externo"
            return cached

        raise