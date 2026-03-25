from __future__ import annotations

"""
ELK Request Logging Middleware
Logs estructurados para ELK stack
"""

import time
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import Response

from app.core.config import settings
from app.core.logger import logger


class ELKLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        # ==============================
        # 🔥 PROTECCIÓN TOTAL (TESTING / DEV)
        # ==============================
        if getattr(settings, "TESTING", False) or settings.APP_ENV != "production":
            return await call_next(request)

        start_time = time.time()

        try:
            # ==============================
            # 🔹 EJECUTAR REQUEST
            # ==============================
            response: Response = await call_next(request)

        except Exception as e:
            # 🔥 NUNCA romper request por logging
            logging.error(f"[ELK] Error antes de response: {e}")
            return await call_next(request)

        # ==============================
        # 🔹 LOGGING SEGURO
        # ==============================
        try:
            latency = round((time.time() - start_time) * 1000, 2)

            trace_id = getattr(request.state, "trace_id", None)
            request_id = getattr(request.state, "request_id", None)

            logger.info(
                "request_completed",
                extra={
                    "trace_id": trace_id,
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "latency_ms": latency,
                },
            )

        except Exception as e:
            # 🔥 si ELK falla → NO afecta API
            logging.error(f"[ELK] Logging error: {e}")

        return response