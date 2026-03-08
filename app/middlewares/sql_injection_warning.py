from __future__ import annotations

import logging
import re
from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SQLInjectionWarningMiddleware(BaseHTTPMiddleware):
    """
    Registra warnings cuando detecta patrones sospechosos en query params.
    No bloquea la petición, solo alerta en logs.
    """

    SUSPICIOUS_PATTERNS = [
        r"'",
        r"--",
        r";",
        r"\bUNION\b",
        r"\bDROP\b",
    ]

    def __init__(self, app):
        super().__init__(app)
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.SUSPICIOUS_PATTERNS
        ]

    async def dispatch(self, request: Request, call_next) -> Response:
        for key, value in request.query_params.multi_items():
            decoded_value = unquote(value)

            for pattern in self._compiled_patterns:
                if pattern.search(decoded_value):
                    logger.warning(
                        "Posible intento de inyección SQL detectado en query params",
                        extra={
                            "path": str(request.url.path),
                            "method": request.method,
                            "query_param": key,
                            "query_value": decoded_value,
                            "client_ip": request.client.host if request.client else None,
                        },
                    )
                    break

        response = await call_next(request)
        return response