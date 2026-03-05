from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        logger.info(
            f"Request recibido | method={method} | path={path} | ip={client_ip}"
        )

        response = await call_next(request)

        process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            f"Request completado | method={method} | path={path} | "
            f"ip={client_ip} | status_code={response.status_code} | "
            f"response_time_ms={process_time_ms}"
        )

        return response