"""
Helpers compartidos para futura modularización de items.

Este archivo todavía no afecta la lógica actual.
Lo dejamos listo para la tarea 37 y para cuando empecemos a partir
items_legacy.py en módulos pequeños.
"""

from __future__ import annotations

from app.api.docs import build_responses
from app.core.request_context import set_current_user_id
from app.models.usuario import Usuario
from app.schemas.common import ErrorResponse


def bind_audit_user(current_user: Usuario | None) -> None:
    """
    Guarda el user_id actual en el contexto de auditoría.
    """
    set_current_user_id(current_user.id if current_user else None)


# Respuestas estándar reutilizables para OpenAPI
ITEM_STANDARD_RESPONSES = build_responses(
    {
        200: {"description": "Operación exitosa"},
        201: {"description": "Recurso creado exitosamente"},
        400: {
            "model": ErrorResponse,
            "description": "Solicitud inválida o regla de negocio incumplida",
        },
        401: {
            "model": ErrorResponse,
            "description": "No autenticado o credenciales inválidas",
        },
        403: {
            "model": ErrorResponse,
            "description": "No autorizado para este recurso",
        },
        404: {
            "model": ErrorResponse,
            "description": "Recurso no encontrado",
        },
        422: {
            "description": "Error de validación en los datos de entrada",
        },
        500: {
            "model": ErrorResponse,
            "description": "Error interno del servidor",
        },
    },
    include_common_errors=False,
)