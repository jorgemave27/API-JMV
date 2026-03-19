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

_consecutive_slow_requests: dict[str, int] = defaultdict(int)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        logger.info(
            "Request recibido | method=%s | path=%s | ip=%s",
            method,
            path,
            client_ip,
        )

        response = await call_next(request)

        process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "Request completado | method=%s | path=%s | ip=%s | status_code=%s | response_time_ms=%s",
            method,
            path,
            client_ip,
            response.status_code,
            process_time_ms,
        )

        slow_threshold_ms = settings.PROFILING_SLOW_REQUEST_THRESHOLD_MS

        if process_time_ms >= slow_threshold_ms:
            _consecutive_slow_requests[path] += 1
            logger.warning(
                "Slow request detectado | path=%s | response_time_ms=%s | consecutive_slow_requests=%s",
                path,
                process_time_ms,
                _consecutive_slow_requests[path],
            )
        else:
            _consecutive_slow_requests[path] = 0

        request.app.state.last_request_profile_candidate = {
            "path": path,
            "method": method,
            "response_time_ms": process_time_ms,
            "status_code": response.status_code,
            "consecutive_slow_requests": _consecutive_slow_requests[path],
        }

        return response
