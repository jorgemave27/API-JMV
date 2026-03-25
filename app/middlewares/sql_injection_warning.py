from __future__ import annotations

import logging
import re
from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

logger = logging.getLogger(__name__)


class SQLInjectionWarningMiddleware(BaseHTTPMiddleware):
    """
    🔥 SAFE VERSION

    ✔ Solo alerta (no bloquea)
    ✔ No rompe request
    ✔ Reduce falsos positivos
    ✔ Controla ruido en logs
    """

    # 🔥 más específicos (menos falsos positivos)
    SUSPICIOUS_PATTERNS = [
        r"(?i)\bunion\b",
        r"(?i)\bdrop\b",
        r"(?i)\bor\b\s+'?1'?\s*=\s*'?1'?",
        r"--",
    ]

    def __init__(self, app):
        super().__init__(app)
        self._compiled_patterns = [
            re.compile(pattern)
            for pattern in self.SUSPICIOUS_PATTERNS
        ]

    def _is_suspicious(self, value: str) -> bool:
        try:
            decoded = unquote(value)

            for pattern in self._compiled_patterns:
                if pattern.search(decoded):
                    return True

        except Exception as e:
            logger.warning(f"[SQL-WARN] Error evaluando valor: {e}")

        return False

    async def dispatch(self, request: Request, call_next) -> Response:

        # ==============================
        # BYPASS TESTING / DEV
        # ==============================
        if getattr(settings, "TESTING", False) or settings.APP_ENV != "production":
            return await call_next(request)

        try:
            for key, value in request.query_params.multi_items():

                # evitar ruido en valores muy largos
                if not value or len(value) > 500:
                    continue

                if self._is_suspicious(value):

                    logger.warning(
                        "[SQL-WARN] Posible intento SQLi",
                        extra={
                            "path": str(request.url.path),
                            "method": request.method,
                            "query_param": key,
                            "client_ip": request.client.host if request.client else None,
                        },
                    )
                    break  # log una sola vez por request

        except Exception as e:
            # nunca romper request
            logger.error(f"[SQL-WARN] Middleware error: {e}")

        return await call_next(request)