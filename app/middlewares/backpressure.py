from __future__ import annotations

"""
🔥 BACKPRESSURE MIDDLEWARE

Controla cuántos requests concurrentes hay en el sistema.

Si hay demasiados:
→ responde 503 (servidor saturado)

🔥 IMPORTANTE:
- No rompe si Redis falla
- No afecta tests
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis_client import get_redis_client
from app.core.config import settings


MAX_QUEUE = 1000
RETRY_AFTER_SECONDS = 2


class BackpressureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):

        # --------------------------------------------------
        # 🔥 NO ejecutar en TESTING
        # --------------------------------------------------
        if getattr(settings, "TESTING", False):
            return await call_next(request)

        redis = None
        key = "api:inflight_requests"
        incremented = False

        try:
            # --------------------------------------------------
            # 🔥 Obtener Redis (seguro)
            # --------------------------------------------------
            try:
                redis = await get_redis_client()
            except Exception:
                return await call_next(request)

            # --------------------------------------------------
            # 🔥 Incrementar contador
            # --------------------------------------------------
            try:
                current = await redis.incr(key)
                incremented = True
                await redis.expire(key, 10)
            except Exception:
                return await call_next(request)

            # --------------------------------------------------
            # 🔥 Saturación
            # --------------------------------------------------
            if current > MAX_QUEUE:

                if incremented:
                    try:
                        await redis.decr(key)
                    except Exception:
                        pass

                return JSONResponse(
                    status_code=503,
                    content={
                        "success": False,
                        "message": "Servidor saturado",
                        "data": None,
                        "metadata": {},
                    },
                    headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
                )

            # --------------------------------------------------
            # 🔥 Continuar request
            # --------------------------------------------------
            response = await call_next(request)
            return response

        finally:
            # --------------------------------------------------
            # 🔥 Decrementar seguro
            # --------------------------------------------------
            if redis and incremented:
                try:
                    await redis.decr(key)
                except Exception:
                    pass