from __future__ import annotations

import logging
import re
from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class ThreatDetectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware de detección básica de payloads sospechosos.

    Busca patrones de:
    - SQL injection
    - XSS
    - Path traversal

    Si detecta algo:
    - registra log CRITICAL
    - retorna 400 con mensaje genérico
    """

    SUSPICIOUS_PATTERNS = [
        # SQLi
        r"(?i)\bunion\b",
        r"(?i)\bdrop\b",
        r"(?i)\bor\b\s+'?1'?\s*=\s*'?1'?",
        r"--",
        r";",
        r"(?i)\bselect\b.+\bfrom\b",
        # XSS
        r"(?i)<script.*?>.*?</script.*?>",
        r"(?i)javascript:",
        r"(?i)onerror\s*=",
        r"(?i)onload\s*=",
        r"(?i)<img.*?>",
        # Path traversal
        r"\.\./",
        r"\.\.\\",
        r"(?i)%2e%2e%2f",
        r"(?i)%2e%2e\\",
    ]

    def __init__(self, app):
        super().__init__(app)
        self._compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SUSPICIOUS_PATTERNS]

    def _contains_suspicious_pattern(self, text: str) -> bool:
        decoded = unquote(text)

        for pattern in self._compiled_patterns:
            if pattern.search(decoded):
                return True

        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        # -------------------------------------------------------------
        # Revisar query params
        # -------------------------------------------------------------
        for key, value in request.query_params.multi_items():
            if self._contains_suspicious_pattern(f"{key}={value}"):
                logger.critical(
                    "Payload sospechoso detectado en query params",
                    extra={
                        "path": str(request.url.path),
                        "method": request.method,
                        "query_param": key,
                        "query_value": value,
                        "client_ip": request.client.host if request.client else None,
                    },
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": "Solicitud inválida",
                        "data": None,
                        "metadata": {},
                    },
                )

        # -------------------------------------------------------------
        # Revisar body en métodos con payload
        # -------------------------------------------------------------
        if request.method in {"POST", "PUT", "PATCH"}:
            body_bytes = await request.body()

            if body_bytes:
                body_text = body_bytes.decode("utf-8", errors="ignore")

                if self._contains_suspicious_pattern(body_text):
                    logger.critical(
                        "Payload sospechoso detectado en request body",
                        extra={
                            "path": str(request.url.path),
                            "method": request.method,
                            "body": body_text[:1000],
                            "client_ip": request.client.host if request.client else None,
                        },
                    )
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "message": "Solicitud inválida",
                            "data": None,
                            "metadata": {},
                        },
                    )

            # ---------------------------------------------------------
            # Reinyectar body para que FastAPI lo pueda volver a leer
            # ---------------------------------------------------------
            async def receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request._receive = receive

        return await call_next(request)
