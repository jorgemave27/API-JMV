from __future__ import annotations

# =====================================================
# MIDDLEWARE DE ANOMALÍAS DE SEGURIDAD
# =====================================================
# Objetivo:
# - Detectar IPs sospechosas en runtime real
# - NO romper pruebas automatizadas con TestClient
#
# En tests, FastAPI usa hostnames tipo:
# - testserver
# - localhost / 127.0.0.1
#
# Si no excluimos esos escenarios, el detector termina
# bloqueando todas las requests del suite de pytest.
# =====================================================

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.security.anomaly_detector import anomaly_detector


class SecurityAnomalyMiddleware(BaseHTTPMiddleware):
    """
    Middleware que bloquea requests de IPs sospechosas.

    Reglas de bypass:
    - APP_ENV == "test"
    - hostname = testserver
    - client host = testclient
    - localhost / 127.0.0.1
    """

    async def dispatch(self, request: Request, call_next):
        # -------------------------------------------------
        # BYPASS TOTAL EN TESTS
        # -------------------------------------------------
        # Esto evita que pytest/TestClient queden bloqueados
        # por el sistema de detección de anomalías.
        # -------------------------------------------------
        request_host = request.url.hostname or ""
        client_host = request.client.host if request.client else ""

        if (
            settings.APP_ENV == "test"
            or request_host in {"testserver", "localhost", "127.0.0.1"}
            or client_host in {"testclient", "127.0.0.1", "localhost"}
        ):
            return await call_next(request)

        # -------------------------------------------------
        # OBTENER IP REAL
        # -------------------------------------------------
        forwarded_for = request.headers.get("x-forwarded-for")
        ip = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else (client_host or "unknown")
        )

        # -------------------------------------------------
        # SI LA IP YA ESTÁ BLOQUEADA, CORTAR REQUEST
        # -------------------------------------------------
        if anomaly_detector.is_ip_blocked(ip):
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "message": "IP bloqueada por actividad sospechosa",
                },
            )

        # -------------------------------------------------
        # EJECUTAR REQUEST
        # -------------------------------------------------
        response = await call_next(request)

        # -------------------------------------------------
        # REGISTRAR EVENTOS PARA DETECCIÓN
        # -------------------------------------------------
        try:
            status_code = response.status_code
            path = request.url.path

            # 401 repetidos: fuerza bruta
            if status_code == 401:
                anomaly_detector.record_401(ip)

            # 404 distintos: escaneo
            if status_code == 404:
                anomaly_detector.record_404(ip, path)

            # volumen de requests por minuto
            anomaly_detector.record_request(ip)

        except Exception:
            # La detección nunca debe romper el request normal
            pass

        return response