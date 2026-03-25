from __future__ import annotations

import logging
import re
from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

logger = logging.getLogger(__name__)


class ThreatDetectionMiddleware(BaseHTTPMiddleware):
    """
    🔥 SAFE VERSION

    ✔ No rompe requests
    ✔ No afecta testing/dev
    ✔ Protección contra payloads maliciosos
    ✔ Control de performance (body limitado)
    """

    SUSPICIOUS_PATTERNS = [
        # SQLi
        r"\bunion\b",
        r"\bdrop\b",
        r"\bor\b\s+'?1'?\s*=\s*'?1'?",
        r"--",
        r";",
        r"\bselect\b.+\bfrom\b",
        # XSS
        r"<script.*?>.*?</script.*?>",
        r"javascript:",
        r"onerror\s*=",
        r"onload\s*=",
        r"<img.*?>",
        # Path traversal
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e%2f",
        r"%2e%2e\\",
    ]

    MAX_BODY_SIZE = 10_000  # 🔥 evitar problemas de performance

    def __init__(self, app):
        super().__init__(app)
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.SUSPICIOUS_PATTERNS
        ]

    def _contains_suspicious_pattern(self, text: str) -> bool:
        try:
            decoded = unquote(text)

            for pattern in self._compiled_patterns:
                if pattern.search(decoded):
                    return True

        except Exception as e:
            logger.warning(f"[THREAT] Error evaluando patrones: {e}")

        return False

    async def dispatch(self, request: Request, call_next) -> Response:

        # ==============================
        #  BYPASS TESTING / DEV
        # ==============================
        if getattr(settings, "TESTING", False) or settings.APP_ENV != "production":
            return await call_next(request)

        try:
            # ==============================
            # QUERY PARAMS
            # ==============================
            for key, value in request.query_params.multi_items():
                if self._contains_suspicious_pattern(f"{key}={value}"):

                    logger.critical(
                        "[THREAT] Query sospechoso",
                        extra={
                            "path": str(request.url.path),
                            "method": request.method,
                            "query_param": key,
                            "client_ip": request.client.host if request.client else None,
                        },
                    )

                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "message": "Solicitud inválida",
                            "data": {},
                            "metadata": {"errors": []},
                        },
                    )

            # ==============================
            # BODY (CONTROLADO)
            # ==============================
            if request.method in {"POST", "PUT", "PATCH"}:

                body_bytes = await request.body()

                if body_bytes:

                    # 🔥 LIMITAR TAMAÑO (performance)
                    if len(body_bytes) > self.MAX_BODY_SIZE:
                        return await call_next(request)

                    body_text = body_bytes.decode("utf-8", errors="ignore")

                    if self._contains_suspicious_pattern(body_text):

                        logger.critical(
                            "[THREAT] Body sospechoso",
                            extra={
                                "path": str(request.url.path),
                                "method": request.method,
                                "client_ip": request.client.host if request.client else None,
                            },
                        )

                        return JSONResponse(
                            status_code=400,
                            content={
                                "success": False,
                                "message": "Solicitud inválida",
                                "data": {},
                                "metadata": {"errors": []},
                            },
                        )

                # ==============================
                # REINYECTAR BODY (SAFE)
                # ==============================
                async def receive():
                    return {
                        "type": "http.request",
                        "body": body_bytes,
                        "more_body": False,
                    }

                request._receive = receive

            # ==============================
            # CONTINUAR
            # ==============================
            return await call_next(request)

        except Exception as e:
            # 🔥 NUNCA romper request por seguridad
            logger.error(f"[THREAT] Middleware error: {e}")
            return await call_next(request)