from __future__ import annotations

import logging
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

from app.core.config import settings

logger = logging.getLogger(__name__)

# =========================================================
# CONFIGURACIÓN
# =========================================================
INDEX_NAME = "items"

# 🔥 FIX: fallback automático si estás fuera de Docker
DEFAULT_ES_URL = getattr(
    settings,
    "ELASTICSEARCH_URL",
    "http://localhost:9200"  # antes: elasticsearch
)

# 🔥 FIX: inicialización segura
try:
    es = Elasticsearch(DEFAULT_ES_URL)
    ES_ENABLED = True
except Exception as e:
    logger.warning("Elasticsearch no disponible: %s", e)
    es = None
    ES_ENABLED = False


# =========================================================
# HELPERS
# =========================================================
def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_item_document(item: Any, keep_consultas_count: int | None = None) -> dict[str, Any]:
    return {
        "name": item.name,
        "description": item.description,
        "price": _safe_float(item.price),
        "categoria_id": item.categoria_id,
        "consultas_count": keep_consultas_count if keep_consultas_count is not None else 0,
        "suggest": {
            "input": [item.name] if item.name else []
        },
    }


def _get_existing_consultas_count(item_id: int) -> int:
    if not ES_ENABLED:
        return 0

    try:
        result = es.get(index=INDEX_NAME, id=item_id)
        source = result.get("_source", {})
        return int(source.get("consultas_count", 0))
    except Exception:
        return 0


# =========================================================
# CREAR ÍNDICE
# =========================================================
def create_index() -> None:
    if not ES_ENABLED:
        logger.warning("Elasticsearch deshabilitado")
        return

    try:
        if es.indices.exists(index=INDEX_NAME):
            logger.info("Índice '%s' ya existe", INDEX_NAME)
            return

        mapping = {
            "mappings": {
                "properties": {
                    "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "description": {"type": "text", "analyzer": "spanish"},
                    "price": {"type": "scaled_float", "scaling_factor": 100},
                    "categoria_id": {"type": "integer"},
                    "consultas_count": {"type": "integer"},
                    "suggest": {"type": "completion"},
                }
            }
        }

        es.indices.create(index=INDEX_NAME, body=mapping)
        logger.info("Índice creado")

    except Exception as exc:
        logger.warning("Elastic OFF: %s", exc)


# =========================================================
# INDEXAR ITEM
# =========================================================
def index_item(item: Any) -> None:
    if not ES_ENABLED:
        return

    try:
        consultas_count = _get_existing_consultas_count(item.id)
        doc = _build_item_document(item, consultas_count)

        es.index(index=INDEX_NAME, id=item.id, document=doc, refresh=True)

    except Exception as exc:
        logger.warning("Elastic OFF (index): %s", exc)


# =========================================================
# UPDATE ITEM
# =========================================================
def update_item(item: Any) -> None:
    if not ES_ENABLED:
        return

    try:
        consultas_count = _get_existing_consultas_count(item.id)
        doc = _build_item_document(item, consultas_count)

        es.update(
            index=INDEX_NAME,
            id=item.id,
            doc=doc,
            doc_as_upsert=True,
            refresh=True,
        )

    except Exception as exc:
        logger.warning("Elastic OFF (update): %s", exc)


# =========================================================
# DELETE ITEM
# =========================================================
def delete_item(item_id: int) -> None:
    if not ES_ENABLED:
        return

    try:
        es.delete(index=INDEX_NAME, id=item_id, refresh=True)
    except NotFoundError:
        pass
    except Exception as exc:
        logger.warning("Elastic OFF (delete): %s", exc)


# =========================================================
# SEARCH
# =========================================================
def search_items(query: str, filters=None, page: int = 1, size: int = 10):
    if not ES_ENABLED:
        return []

    try:
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "description"],
                    "fuzziness": "AUTO",
                }
            }
        }

        res = es.search(index=INDEX_NAME, body=body)
        return res.get("hits", {}).get("hits", [])

    except Exception as exc:
        logger.warning("Elastic OFF (search): %s", exc)
        return []


# =========================================================
# SUGGEST
# =========================================================
def suggest_items(query: str, size: int = 5):
    if not ES_ENABLED:
        return []

    try:
        body = {
            "suggest": {
                "item-suggest": {
                    "prefix": query,
                    "completion": {"field": "suggest", "size": size},
                }
            }
        }

        res = es.search(index=INDEX_NAME, body=body)
        options = res.get("suggest", {}).get("item-suggest", [{}])[0].get("options", [])

        return [opt.get("text") for opt in options if opt.get("text")]

    except Exception as exc:
        logger.warning("Elastic OFF (suggest): %s", exc)
        return []


# =========================================================
# POPULARIDAD
# =========================================================
def increment_item_popularity(item_id: int) -> None:
    if not ES_ENABLED:
        return

    try:
        es.update(
            index=INDEX_NAME,
            id=item_id,
            script={
                "source": "ctx._source.consultas_count += 1",
                "lang": "painless",
            },
            refresh=True,
        )
    except Exception:
        pass