from __future__ import annotations

import hashlib
import logging
from typing import List

from openai import OpenAI, OpenAIError

from app.core.config import settings
from app.search.elasticsearch_client import search_items

logger = logging.getLogger(__name__)

# =========================================================
# CLIENT SAFE (NO TRUENA SI NO HAY SALDO)
# =========================================================
client = None

try:
    if getattr(settings, "OPENAI_API_KEY", None):
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
except Exception:
    client = None


# =========================================================
# CACHE SIMPLE
# =========================================================
_CACHE = {}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _get_cached(key: str):
    return _CACHE.get(key)


def _set_cache(key: str, value):
    _CACHE[key] = value


# =========================================================
# CLASIFICAR ITEM (SAFE)
# =========================================================
def classify_item(nombre: str, descripcion: str) -> str:
    cache_key = _hash(nombre + descripcion)

    if cached := _get_cached(cache_key):
        return cached

    # 🔥 FALLBACK SI NO HAY LLM
    if not client:
        categoria = "general"
        _set_cache(cache_key, categoria)
        return categoria

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{
                "role": "user",
                "content": f"Clasifica este producto en una sola palabra: {nombre} - {descripcion}"
            }],
        )

        categoria = response.choices[0].message.content.strip()

    except OpenAIError:
        categoria = "general"

    _set_cache(cache_key, categoria)

    return categoria


# =========================================================
# RESPONDER PREGUNTAS (SAFE)
# =========================================================
def answer_product_question(pregunta: str) -> str:
    cache_key = _hash(pregunta)

    if cached := _get_cached(cache_key):
        return cached

    # 🔥 FALLBACK SI NO HAY LLM
    if not client:
        respuesta = "Modo demo: no hay LLM disponible"
        _set_cache(cache_key, respuesta)
        return respuesta

    try:
        resultados = search_items(pregunta)

        context_items = [
            hit.get("_source", {}) for hit in resultados[:5]
        ]

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{
                "role": "user",
                "content": f"Responde con base en estos productos: {context_items}. Pregunta: {pregunta}"
            }],
        )

        respuesta = response.choices[0].message.content.strip()

    except OpenAIError:
        respuesta = "Modo fallback: error LLM"

    _set_cache(cache_key, respuesta)

    return respuesta