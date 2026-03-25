from __future__ import annotations

"""
BACKPRESSURE MIDDLEWARE (SAFE VERSION)

Controla requests concurrentes.

✔ No rompe si Redis falla
✔ No rompe en Docker
✔ No fuga contadores
✔ Async correcto
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request

from app.core.redis_client import get_redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_QUEUE = 1000
RETRY_AFTER_SECONDS = 2


class BackpressureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        # ==============================
        # DESACTIVAR EN TESTING / DEV
        # ==============================
        if getattr(settings, "TESTING", False) or settings.APP_ENV != "production":
            return await call_next(request)

        redis = None
        key = "api:inflight_requests"
        incremented = False

        try:
            # ==============================
            # OBTENER REDIS (SEGURO)
            # ==============================
            try:
                redis = await get_redis_client()
            except Exception as e:
                logger.warning(f"[BACKPRESSURE] Redis no disponible: {e}")
                return await call_next(request)

            # ==============================
            # INCREMENTAR CONTADOR
            # ==============================
            try:
                current = await redis.incr(key)
                incremented = True

                # TTL para evitar fugas si algo truena
                await redis.expire(key, 10)

            except Exception as e:
                logger.warning(f"[BACKPRESSURE] Error incrementando contador: {e}")
                return await call_next(request)

            # ==============================
            # SATURACIÓN
            # ==============================
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
                        "data": {},
                        "metadata": {"errors": []},
                    },
                    headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
                )

            # ==============================
            # CONTINUAR REQUEST
            # ==============================
            try:
                response = await call_next(request)
                return response

            except Exception as e:
                logger.error(f"[BACKPRESSURE] Error en request: {e}")
                raise  # 🔥 importante: no ocultar errores reales

        finally:
            # ==============================
            # DECREMENTO SEGURO
            # ==============================
            if redis and incremented:
                try:
                    await redis.decr(key)
                except Exception as e:
                    logger.warning(f"[BACKPRESSURE] Error decrementando: {e}")