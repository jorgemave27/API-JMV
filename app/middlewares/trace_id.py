from __future__ import annotations

"""
Trace ID Middleware


Garantiza que cada request tenga un trace_id
para correlacionar logs entre servicios.
"""

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

TRACE_HEADER = "X-Trace-Id"


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        trace_id = request.headers.get(TRACE_HEADER)

        if not trace_id:
            trace_id = str(uuid.uuid4())

        request.state.trace_id = trace_id

        response = await call_next(request)

        response.headers[TRACE_HEADER] = trace_id

        return response
