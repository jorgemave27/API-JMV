from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings

logger = logging.getLogger(__name__)

# contador controlado
_consecutive_slow_requests: dict[str, int] = defaultdict(int)
MAX_TRACKED_PATHS = 1000  # evita fuga de memoria


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:

        start_time = time.perf_counter()

        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        # ==============================
        # LOG INICIAL (CONTROLADO)
        # ==============================
        if settings.APP_ENV == "production":
            logger.info(
                "[REQ] Start | %s %s | ip=%s",
                method,
                path,
                client_ip,
            )

        try:
            # ==============================
            # EJECUTAR REQUEST
            # ==============================
            response: Response = await call_next(request)

        except Exception as e:
            logger.error(f"[REQ] Error en request {method} {path}: {e}")
            raise  # 🔥 no ocultar errores reales

        process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ==============================
        # LOG FINAL (CONTROLADO)
        # ==============================
        if settings.APP_ENV == "production":
            logger.info(
                "[REQ] End | %s %s | status=%s | time=%sms | ip=%s",
                method,
                path,
                response.status_code,
                process_time_ms,
                client_ip,
            )

        # ==============================
        # CONTROL DE LENTITUD
        # ==============================
        slow_threshold_ms = settings.PROFILING_SLOW_REQUEST_THRESHOLD_MS

        try:
            if process_time_ms >= slow_threshold_ms:
                _consecutive_slow_requests[path] += 1

                logger.warning(
                    "[REQ] Slow | path=%s | time=%s ms | consecutive=%s",
                    path,
                    process_time_ms,
                    _consecutive_slow_requests[path],
                )
            else:
                _consecutive_slow_requests[path] = 0

            # evitar crecimiento infinito del dict
            if len(_consecutive_slow_requests) > MAX_TRACKED_PATHS:
                _consecutive_slow_requests.clear()

        except Exception as e:
            logger.warning(f"[REQ] Error tracking slow requests: {e}")

        # ==============================
        # PERFILADO (SAFE)
        # ==============================
        try:
            request.app.state.last_request_profile_candidate = {
                "path": path,
                "method": method,
                "response_time_ms": process_time_ms,
                "status_code": response.status_code,
                "consecutive_slow_requests": _consecutive_slow_requests[path],
            }
        except Exception as e:
            logger.warning(f"[REQ] Error guardando candidato profiler: {e}")

        return response