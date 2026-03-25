from __future__ import annotations

import asyncio
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from app.api.v1.endpoints.chaos import CHAOS_STATE
except Exception:
    CHAOS_STATE = {
        "slow_db": False,
        "redis_down": False,
        "memory_pressure": False,
    }


class ChaosMiddleware(BaseHTTPMiddleware):
    """
    Middleware global para Chaos Engineering

    - No bloquea event loop (async sleep)
    - No rompe en testing
    - No rompe requests si falla
    """

    async def dispatch(self, request: Request, call_next):

        # ==============================
        # DESACTIVAR EN TESTING
        # ==============================
        if getattr(settings, "TESTING", False):
            return await call_next(request)

        try:
            # ==============================
            # LATENCIA (NO BLOQUEANTE)
            # ==============================
            if CHAOS_STATE.get("slow_db"):
                await asyncio.sleep(2)  # ✅ FIX CRÍTICO

            # ==============================
            # MEMORY PRESSURE CONTROLADO
            # ==============================
            if CHAOS_STATE.get("memory_pressure"):
                try:
                    _ = [0] * 200_000  # 🔽 reducido para no matar Docker
                except Exception as e:
                    logger.warning(f"[CHAOS] memory_pressure error: {e}")

            # ==============================
            # CONTINUAR REQUEST
            # ==============================
            response = await call_next(request)
            return response

        except Exception as e:
            # NUNCA romper request global
            logger.error(f"[CHAOS] Middleware error: {e}")

            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Chaos middleware error",
                    "data": {},
                    "metadata": {"errors": []},
                },
            )