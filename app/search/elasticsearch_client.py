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
DEFAULT_ES_URL = getattr(settings, "ELASTICSEARCH_URL", "http://elasticsearch:9200")

# Cliente singleton
es = Elasticsearch(DEFAULT_ES_URL)


# =========================================================
# HELPERS
# =========================================================
def _safe_float(value: Any) -> float | None:
    """
    Convierte valores numéricos a float de forma segura.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_item_document(item: Any, keep_consultas_count: int | None = None) -> dict[str, Any]:
    """
    Construye el documento que se indexará en Elasticsearch.

    keep_consultas_count:
    - Si se manda un entero, se conserva ese valor.
    - Si es None, se inicializa en 0.
    """
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
    """
    Recupera el contador actual de consultas del documento para no perder
    popularidad en updates/reindex.
    """
    try:
        result = es.get(index=INDEX_NAME, id=item_id)
        source = result.get("_source", {})
        return int(source.get("consultas_count", 0))
    except Exception:
        return 0


# =========================================================
# CREAR ÍNDICE (SI NO EXISTE)
# =========================================================
def create_index() -> None:
    """
    Crea el índice 'items' si no existe.
    Incluye mapping para:
    - búsqueda full-text
    - keyword para agregaciones
    - scaled_float para precio
    - completion suggester
    """
    try:
        if es.indices.exists(index=INDEX_NAME):
            logger.info("Índice Elasticsearch '%s' ya existe", INDEX_NAME)
            return

        mapping = {
            "mappings": {
                "properties": {
                    "name": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword"
                            }
                        }
                    },
                    "description": {
                        "type": "text",
                        "analyzer": "spanish"
                    },
                    "price": {
                        "type": "scaled_float",
                        "scaling_factor": 100
                    },
                    "categoria_id": {
                        "type": "integer"
                    },
                    "consultas_count": {
                        "type": "integer"
                    },
                    "suggest": {
                        "type": "completion"
                    }
                }
            }
        }

        es.indices.create(index=INDEX_NAME, body=mapping)
        logger.info("Índice Elasticsearch '%s' creado correctamente", INDEX_NAME)

    except Exception as exc:
        logger.error("Error creando índice Elasticsearch '%s': %s", INDEX_NAME, exc, exc_info=True)
        raise


# =========================================================
# INDEXAR ITEM
# =========================================================
def index_item(item: Any) -> None:
    """
    Indexa un item completo en Elasticsearch.

    Si el item ya existía antes y se reindexa, intenta conservar el
    consultas_count para no perder popularidad.
    """
    try:
        consultas_count = _get_existing_consultas_count(item.id)
        doc = _build_item_document(item, keep_consultas_count=consultas_count)

        es.index(
            index=INDEX_NAME,
            id=item.id,
            document=doc,
            refresh=True,
        )

        logger.info("Item %s indexado en Elasticsearch", item.id)

    except Exception as exc:
        logger.error("Error indexando item %s en Elasticsearch: %s", getattr(item, "id", None), exc, exc_info=True)
        raise


# =========================================================
# UPDATE ITEM
# =========================================================
def update_item(item: Any) -> None:
    """
    Actualiza un item en Elasticsearch.

    Mantiene el valor actual de consultas_count para no reiniciar
    la popularidad del documento.
    """
    try:
        consultas_count = _get_existing_consultas_count(item.id)
        doc = _build_item_document(item, keep_consultas_count=consultas_count)

        # Con doc_as_upsert=True, si no existe lo crea.
        es.update(
            index=INDEX_NAME,
            id=item.id,
            doc=doc,
            doc_as_upsert=True,
            refresh=True,
        )

        logger.info("Item %s actualizado en Elasticsearch", item.id)

    except Exception as exc:
        logger.error("Error actualizando item %s en Elasticsearch: %s", getattr(item, "id", None), exc, exc_info=True)
        raise


# =========================================================
# DELETE ITEM
# =========================================================
def delete_item(item_id: int) -> None:
    """
    Elimina un documento del índice Elasticsearch.
    Si no existe, no rompe el flujo.
    """
    try:
        es.delete(
            index=INDEX_NAME,
            id=item_id,
            refresh=True,
        )
        logger.info("Item %s eliminado de Elasticsearch", item_id)

    except NotFoundError:
        logger.warning("Item %s no existía en Elasticsearch; se omite delete", item_id)

    except Exception as exc:
        logger.error("Error eliminando item %s de Elasticsearch: %s", item_id, exc, exc_info=True)
        raise


# =========================================================
# SEARCH (FUZZY + FILTERS + HIGHLIGHT + PAGINACIÓN)
# =========================================================
def search_items(
    query: str,
    filters: dict[str, Any] | None = None,
    page: int = 1,
    size: int = 10,
) -> list[dict[str, Any]]:
    """
    Busca items usando Elasticsearch con:
    - búsqueda full-text en name y description
    - fuzziness AUTO
    - filtros por categoría y rango de precios
    - highlight
    - paginación

    Firma compatible con items_legacy.py:
        search_items(query, filters, page, size)
    """
    try:
        filters = filters or {}

        categoria_id = filters.get("categoria_id")
        precio_min = filters.get("precio_min")
        precio_max = filters.get("precio_max")

        must = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "description"],
                    "fuzziness": "AUTO"
                }
            }
        ]

        filter_clauses: list[dict[str, Any]] = []

        if categoria_id is not None:
            filter_clauses.append(
                {
                    "term": {
                        "categoria_id": categoria_id
                    }
                }
            )

        if precio_min is not None or precio_max is not None:
            range_filter: dict[str, Any] = {}

            if precio_min is not None:
                range_filter["gte"] = precio_min

            if precio_max is not None:
                range_filter["lte"] = precio_max

            filter_clauses.append(
                {
                    "range": {
                        "price": range_filter
                    }
                }
            )

        from_ = (page - 1) * size

        body = {
            "from": from_,
            "size": size,
            "query": {
                "bool": {
                    "must": must,
                    "filter": filter_clauses
                }
            },
            "highlight": {
                "pre_tags": ["<em>"],
                "post_tags": ["</em>"],
                "fields": {
                    "name": {},
                    "description": {}
                }
            }
        }

        res = es.search(index=INDEX_NAME, body=body)
        hits = res.get("hits", {}).get("hits", [])

        logger.info(
            "Búsqueda Elasticsearch ejecutada: query='%s', page=%s, size=%s, resultados=%s",
            query,
            page,
            size,
            len(hits),
        )

        return hits

    except Exception as exc:
        logger.error("Error en search_items(query=%s): %s", query, exc, exc_info=True)
        raise


# =========================================================
# SUGGEST (AUTOCOMPLETE)
# =========================================================
def suggest_items(query: str, size: int = 5) -> list[str]:
    """
    Devuelve hasta `size` sugerencias de nombres de items.

    Ojo:
    El completion suggester no siempre ordena directamente por un campo arbitrario
    como consultas_count en la consulta.
    Por eso aquí:
    1. pedimos varias opciones
    2. las ordenamos manualmente por consultas_count
    3. devolvemos solo los textos finales
    """
    try:
        fetch_size = max(size * 3, 10)

        body = {
            "suggest": {
                "item-suggest": {
                    "prefix": query,
                    "completion": {
                        "field": "suggest",
                        "size": fetch_size,
                        "skip_duplicates": True
                    }
                }
            }
        }

        res = es.search(index=INDEX_NAME, body=body)
        options = res.get("suggest", {}).get("item-suggest", [{}])[0].get("options", [])

        # Ordenar por popularidad (consultas_count), mayor primero
        sorted_options = sorted(
            options,
            key=lambda opt: opt.get("_source", {}).get("consultas_count", 0),
            reverse=True,
        )

        suggestions: list[str] = []
        seen: set[str] = set()

        for option in sorted_options:
            text = option.get("text")
            if not text:
                continue
            if text in seen:
                continue
            seen.add(text)
            suggestions.append(text)

            if len(suggestions) >= size:
                break

        logger.info("Sugerencias Elasticsearch para '%s': %s", query, suggestions)
        return suggestions

    except Exception as exc:
        logger.error("Error en suggest_items(query=%s): %s", query, exc, exc_info=True)
        raise


# =========================================================
# POPULARIDAD / CONSULTAS
# =========================================================
def increment_item_popularity(item_id: int) -> None:
    """
    Incrementa el contador consultas_count del documento.
    Esto se usa para ordenar sugerencias por popularidad.
    """
    try:
        es.update(
            index=INDEX_NAME,
            id=item_id,
            script={
                "source": """
                    if (ctx._source.consultas_count == null) {
                        ctx._source.consultas_count = 1;
                    } else {
                        ctx._source.consultas_count += 1;
                    }
                """,
                "lang": "painless",
            },
            refresh=True,
        )

        logger.info("Popularidad incrementada para item %s en Elasticsearch", item_id)

    except NotFoundError:
        logger.warning(
            "No se pudo incrementar popularidad del item %s porque no existe en Elasticsearch",
            item_id,
        )

    except Exception as exc:
        logger.error("Error incrementando popularidad item %s: %s", item_id, exc, exc_info=True)
        raise