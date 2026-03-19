from __future__ import annotations

from app.schemas.common import ErrorResponse

COMMON_ERROR_RESPONSES = {
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
        "description": "Error de validación de datos de entrada",
    },
    500: {
        "model": ErrorResponse,
        "description": "Error interno del servidor",
    },
}


def build_responses(
    success_responses: dict[int, dict] | None = None,
    include_common_errors: bool = True,
) -> dict[int, dict]:
    responses: dict[int, dict] = {}

    if success_responses:
        responses.update(success_responses)

    if include_common_errors:
        for status_code, config in COMMON_ERROR_RESPONSES.items():
            responses.setdefault(status_code, config)

    return responses
