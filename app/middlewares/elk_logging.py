from __future__ import annotations

"""
ELK Request Logging Middleware
Logs estructurados para ELK stack.
"""

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import logger


class ELKLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        start_time = time.time()

        response = await call_next(request)

        latency = round((time.time() - start_time) * 1000, 2)

        trace_id = getattr(request.state, "trace_id", None)

        logger.info(
            "request_completed",
            extra={
                "trace_id": trace_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "latency_ms": latency,
            },
        )

        return response
