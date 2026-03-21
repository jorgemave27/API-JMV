import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

try:
    from app.api.v1.endpoints.chaos import CHAOS_STATE
except Exception:
    CHAOS_STATE = {
        "slow_db": False,
        "redis_down": False,
        "memory_pressure": False
    }


class ChaosMiddleware(BaseHTTPMiddleware):
    """
    Middleware global para Chaos Engineering
    """

    async def dispatch(self, request, call_next):
        try:
            # 🔥 LATENCIA GLOBAL
            if CHAOS_STATE.get("slow_db"):
                time.sleep(2)

            # 🔥 MEMORY PRESSURE CONTROLADO
            if CHAOS_STATE.get("memory_pressure"):
                _ = [0] * 500_000  # ⚠️ seguro (no rompe)

            response = await call_next(request)
            return response

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"Chaos handled error: {str(e)}"
                }
            )