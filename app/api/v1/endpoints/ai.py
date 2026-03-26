from fastapi import APIRouter

from app.ai.llm_service import (
    classify_item,
    answer_product_question,
)

router = APIRouter()


# =========================================================
# CLASIFICAR ITEM
# =========================================================
@router.post("/items/clasificar-automaticamente")
def clasificar_item(data: dict):
    nombre = data.get("nombre")
    descripcion = data.get("descripcion")

    categoria = classify_item(nombre, descripcion)

    return {
        "success": True,
        "message": "Clasificación generada",
        "data": {"categoria_sugerida": categoria},
        "metadata": {},
    }


# =========================================================
# PREGUNTAR AL CATÁLOGO
# =========================================================
@router.post("/catalogo/preguntar")
def preguntar_catalogo(data: dict):
    pregunta = data.get("pregunta")

    respuesta = answer_product_question(pregunta)

    return {
        "success": True,
        "message": "Respuesta generada",
        "data": {"respuesta": respuesta},
        "metadata": {},
    }