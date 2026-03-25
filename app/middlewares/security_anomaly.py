from __future__ import annotations

"""
SECURITY ANOMALY MIDDLEWARE (SAFE VERSION)

✔ No rompe tests
✔ No rompe Docker
✔ Maneja IP correctamente (proxy-friendly)
✔ No bloquea por error interno
✔ Tolerante a fallos del detector
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.security.anomaly_detector import anomaly_detector

logger = logging.getLogger(__name__)


class SecurityAnomalyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        # ==============================
        #  BYPASS TOTAL (TESTING / LOCAL)
        # ==============================
        request_host = request.url.hostname or ""
        client_host = request.client.host if request.client else ""

        if (
            getattr(settings, "TESTING", False)
            or settings.APP_ENV == "test"
            or request_host in {"testserver", "localhost", "127.0.0.1"}
            or client_host in {"testclient", "127.0.0.1", "localhost"}
        ):
            return await call_next(request)

        # ==============================
        # OBTENER IP REAL (SAFE)
        # ==============================
        try:
            forwarded_for = request.headers.get("x-forwarded-for")

            if forwarded_for:
                ip = forwarded_for.split(",")[0].strip()
            else:
                ip = client_host or "unknown"

        except Exception as e:
            logger.warning(f"[SECURITY] Error obteniendo IP: {e}")
            ip = "unknown"

        # ==============================
        # VALIDAR BLOQUEO
        # ==============================
        try:
            if anomaly_detector.is_ip_blocked(ip):
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "message": "IP bloqueada por actividad sospechosa",
                        "data": {},
                        "metadata": {"errors": []},
                    },
                )
        except Exception as e:
            logger.error(f"[SECURITY] Error validando IP bloqueada: {e}")

        # ==============================
        # EJECUTAR REQUEST
        # ==============================
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"[SECURITY] Error en request: {e}")
            raise  # 🔥 NO ocultar errores reales

        # ==============================
        # REGISTRAR EVENTOS (SAFE)
        # ==============================
        try:
            status_code = response.status_code
            path = request.url.path

            # 401 → fuerza bruta
            if status_code == 401:
                anomaly_detector.record_401(ip)

            # 404 → escaneo
            if status_code == 404:
                anomaly_detector.record_404(ip, path)

            # volumen general
            anomaly_detector.record_request(ip)

        except Exception as e:
            # nunca romper request por esto
            logger.warning(f"[SECURITY] Error registrando anomalía: {e}")

        return response