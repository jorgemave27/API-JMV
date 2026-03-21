from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis_client import get_redis_client

MAX_QUEUE = 1000
RETRY_AFTER_SECONDS = 2


class BackpressureMiddleware(BaseHTTPMiddleware):
    """
    Middleware de control de carga global.

    - Cuenta requests activos en Redis
    - Si supera threshold → rechaza con 503
    """

    async def dispatch(self, request, call_next):
        redis = await get_redis_client()

        key = "api:inflight_requests"

        try:
            current = await redis.incr(key)
            await redis.expire(key, 10)

            if current > MAX_QUEUE:
                await redis.decr(key)

                return JSONResponse(
                    status_code=503,
                    content={
                        "success": False,
                        "message": "Servidor saturado, intenta nuevamente",
                    },
                    headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
                )

            response = await call_next(request)

            return response

        finally:
            try:
                await redis.decr(key)
            except Exception:
                pass