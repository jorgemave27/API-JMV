from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import (
    reset_current_client_ip,
    reset_current_user_id,
    set_current_client_ip,
    set_current_user_id,
)


class AuditContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware para inicializar y limpiar el contexto de auditoría.

    Responsabilidades:
    - guardar la IP del cliente al inicio del request
    - inicializar user_id como None
    - limpiar ambos valores al finalizar el request

    Nota:
    - El user_id real se setea dentro de los endpoints autenticados,
      justo antes de operaciones que escriben en base de datos.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # -------------------------------------------------------------
        # Obtener IP del cliente desde el request
        # -------------------------------------------------------------
        client_ip = request.client.host if request.client else None

        # -------------------------------------------------------------
        # Guardar valores en contextvars
        # -------------------------------------------------------------
        ip_token = set_current_client_ip(client_ip)
        user_token = set_current_user_id(None)

        try:
            response = await call_next(request)
            return response
        finally:
            # ---------------------------------------------------------
            # Limpiar contexto para evitar "fugas" entre requests
            # ---------------------------------------------------------
            reset_current_client_ip(ip_token)
            reset_current_user_id(user_token)
