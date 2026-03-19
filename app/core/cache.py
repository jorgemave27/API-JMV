from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Cliente singleton de Redis para reutilizar la conexión
_redis_client: Redis | None = None

# Prefijos y keys base para organizar la caché
ITEM_CACHE_PREFIX = "api-jmv:item:"
ITEMS_LIST_CACHE_PREFIX = "api-jmv:items:list:"
ITEMS_LIST_ALL_PAGES_KEY = "api-jmv:items:list:all-pages"
ITEMS_LIST_FIRST_PAGES_KEY = "api-jmv:items:list:first-pages"
ITEM_PAGES_INDEX_PREFIX = "api-jmv:items:item-pages:"
LIST_META_SUFFIX = ":meta"


def get_redis_client() -> Redis | None:
    """
    Devuelve el cliente de Redis si la caché está habilitada y Redis está disponible.
    Si Redis falla, retorna None para que la API siga funcionando sin caché.
    """
    global _redis_client

    if not settings.CACHE_ENABLED:
        return None

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,  # para trabajar con strings normales en vez de bytes
            )
            _redis_client.ping()
        except RedisError as exc:
            logger.warning("Redis no disponible. Caché deshabilitada: %s", exc)
            _redis_client = None

    return _redis_client


def _serialize(value: Any) -> str:
    """
    Convierte cualquier valor Python a JSON string para guardarlo en Redis.
    default=str ayuda a serializar fechas, decimales, etc.
    """
    return json.dumps(value, default=str)


def _deserialize(value: str | None) -> Any:
    """
    Convierte el JSON string guardado en Redis a objeto Python.
    """
    if value is None:
        return None
    return json.loads(value)


def get_cache(key: str) -> Any | None:
    """
    Lee un valor de caché por key.
    Si Redis falla, retorna None y la app sigue con BD.
    """
    client = get_redis_client()
    if client is None:
        return None

    try:
        value = client.get(key)
        return _deserialize(value)
    except RedisError as exc:
        logger.warning("Error leyendo caché key=%s: %s", key, exc)
        return None


def set_cache(key: str, value: Any, ttl: int) -> None:
    """
    Guarda un valor en caché con TTL (tiempo de vida en segundos).
    """
    client = get_redis_client()
    if client is None:
        return

    try:
        client.setex(key, ttl, _serialize(value))
    except RedisError as exc:
        logger.warning("Error escribiendo caché key=%s: %s", key, exc)


def delete_cache(key: str) -> None:
    """
    Elimina una key específica de caché.
    """
    client = get_redis_client()
    if client is None:
        return

    try:
        client.delete(key)
    except RedisError as exc:
        logger.warning("Error eliminando caché key=%s: %s", key, exc)


def build_item_cache_key(item_id: int) -> str:
    """
    Construye la key de caché para un item individual.
    Ejemplo: api-jmv:item:15
    """
    return f"{ITEM_CACHE_PREFIX}{item_id}"


def build_items_list_signature(params: dict[str, Any]) -> str:
    """
    Genera una firma determinística para los parámetros del listado.

    Nota:
    - Se usa SHA-256 para evitar alertas de seguridad de Bandit por uso de MD5.
    - Aquí no se usa con fines criptográficos sensibles, sino para construir keys
      de caché estables y únicas.
    """
    normalized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_items_list_cache_key(signature: str, page: int) -> str:
    """
    Construye la key de caché para una página del listado.
    """
    return f"{ITEMS_LIST_CACHE_PREFIX}{signature}:page:{page}"


def build_item_pages_index_key(item_id: int) -> str:
    """
    Key que guarda en qué páginas cacheadas apareció un item.
    Sirve para invalidación inteligente.
    """
    return f"{ITEM_PAGES_INDEX_PREFIX}{item_id}"


def build_list_meta_key(cache_key: str) -> str:
    """
    Key para guardar metadata asociada a una página cacheada.
    """
    return f"{cache_key}{LIST_META_SUFFIX}"


def register_list_cache(
    *,
    cache_key: str,
    page: int,
    ttl: int,
    item_ids: list[int],
    params: dict[str, Any],
) -> None:
    """
    Registra metadata de una página cacheada:
    - la página
    - qué items contiene
    - qué parámetros originaron esa página

    Esto nos permite invalidar de forma más inteligente después.
    """
    client = get_redis_client()
    if client is None:
        return

    meta = {
        "page": page,
        "item_ids": item_ids,
        "params": params,
    }

    meta_key = build_list_meta_key(cache_key)

    try:
        # Guardamos la referencia global de páginas cacheadas
        client.sadd(ITEMS_LIST_ALL_PAGES_KEY, cache_key)

        # Si es la página 1, la registramos aparte porque suele ser la más afectada
        if page == 1:
            client.sadd(ITEMS_LIST_FIRST_PAGES_KEY, cache_key)

        # Guardamos metadata de esta página con el mismo TTL
        client.setex(meta_key, ttl, _serialize(meta))

        # Para cada item de la página, guardamos relación item -> páginas donde aparece
        for item_id in item_ids:
            client.sadd(build_item_pages_index_key(item_id), cache_key)
    except RedisError as exc:
        logger.warning("Error registrando metadata de caché list=%s: %s", cache_key, exc)


def _cleanup_list_indexes(cache_key: str, item_ids: list[int], page: int) -> None:
    """
    Limpia los índices auxiliares cuando invalidamos una página cacheada.
    """
    client = get_redis_client()
    if client is None:
        return

    try:
        client.srem(ITEMS_LIST_ALL_PAGES_KEY, cache_key)

        if page == 1:
            client.srem(ITEMS_LIST_FIRST_PAGES_KEY, cache_key)

        for item_id in item_ids:
            client.srem(build_item_pages_index_key(item_id), cache_key)
    except RedisError as exc:
        logger.warning("Error limpiando índices de caché page=%s: %s", cache_key, exc)


def invalidate_list_page(cache_key: str) -> None:
    """
    Invalida una página específica de listado:
    - borra el payload cacheado
    - borra su metadata
    - limpia sus índices auxiliares
    """
    client = get_redis_client()
    if client is None:
        return

    meta_key = build_list_meta_key(cache_key)

    try:
        meta_raw = client.get(meta_key)
        meta = _deserialize(meta_raw) if meta_raw else {}

        item_ids = meta.get("item_ids", [])
        page = meta.get("page", 0)

        client.delete(cache_key)
        client.delete(meta_key)

        _cleanup_list_indexes(cache_key, item_ids, page)
    except RedisError as exc:
        logger.warning("Error invalidando list page=%s: %s", cache_key, exc)


def invalidate_first_page_list_caches() -> None:
    """
    Invalida todas las primeras páginas cacheadas.
    Esto es útil especialmente al crear items nuevos.
    """
    client = get_redis_client()
    if client is None:
        return

    try:
        keys = client.smembers(ITEMS_LIST_FIRST_PAGES_KEY)
        for key in keys:
            invalidate_list_page(key)
    except RedisError as exc:
        logger.warning("Error invalidando primeras páginas de caché: %s", exc)


def invalidate_list_caches_for_item(item_id: int, include_first_pages: bool = True) -> None:
    """
    Invalida todas las páginas cacheadas donde apareció un item específico.
    Opcionalmente también invalida las primeras páginas.
    """
    client = get_redis_client()
    if client is None:
        return

    try:
        indexed_pages = client.smembers(build_item_pages_index_key(item_id))
        for cache_key in indexed_pages:
            invalidate_list_page(cache_key)

        client.delete(build_item_pages_index_key(item_id))

        if include_first_pages:
            invalidate_first_page_list_caches()
    except RedisError as exc:
        logger.warning("Error invalidando páginas asociadas al item=%s: %s", item_id, exc)


def get_cache_stats() -> dict[str, Any]:
    """
    Obtiene estadísticas básicas de Redis:
    - si está disponible
    - cuántas keys hay
    - memoria usada
    """
    client = get_redis_client()
    if client is None:
        return {
            "available": False,
            "keys": 0,
            "used_memory": "0B",
            "used_memory_bytes": 0,
        }

    try:
        info = client.info("memory")
        return {
            "available": True,
            "keys": client.dbsize(),
            "used_memory": info.get("used_memory_human", "N/A"),
            "used_memory_bytes": info.get("used_memory", 0),
        }
    except RedisError as exc:
        logger.warning("Error obteniendo stats de Redis: %s", exc)
        return {
            "available": False,
            "keys": 0,
            "used_memory": "0B",
            "used_memory_bytes": 0,
        }
