"""
Middleware de detección de intrusiones y anomalías.

Este middleware:

1. Verifica si una IP está bloqueada
2. Registra volumen de requests
3. Detecta fuerza bruta (401)
4. Detecta escaneo de endpoints (404)

Si una IP está bloqueada devuelve 403 inmediatamente.
"""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.database.database import SessionLocal
from app.models.security_event import SecurityEvent
from app.security.anomaly_detector import AnomalyDetector


# -----------------------------------------------------
# Instancia global del detector
# -----------------------------------------------------
detector = AnomalyDetector()


class SecurityAnomalyMiddleware(BaseHTTPMiddleware):
    """
    Middleware principal de seguridad.
    """

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """
        Obtiene la IP cliente.

        Prioridad:
        1. X-Forwarded-For
        2. request.client.host
        3. unknown
        """
        forwarded_for = request.headers.get("x-forwarded-for")

        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        if request.client and request.client.host:
            return request.client.host

        return "unknown"

    @staticmethod
    def _save_security_event(
        *,
        ip: str,
        tipo_evento: str,
        detalles: str,
        accion_tomada: str,
        pais: str | None = None,
    ) -> None:
        """
        Persiste un evento de seguridad en la base de datos.
        """
        db = SessionLocal()

        try:
            evento = SecurityEvent(
                ip=ip,
                tipo_evento=tipo_evento,
                detalles=detalles,
                accion_tomada=accion_tomada,
                pais=pais,
            )
            db.add(evento)
            db.commit()

        except Exception:
            db.rollback()

        finally:
            db.close()

    async def dispatch(self, request: Request, call_next):
        """
        Flujo principal del middleware.
        """
        ip = self._get_client_ip(request)

        # ----------------------------------------
        # verificar si la IP está bloqueada
        # ----------------------------------------
        if detector.is_ip_blocked(ip):
            self._save_security_event(
                ip=ip,
                tipo_evento="ip_blocked",
                detalles=f"Intento de acceso bloqueado a path={request.url.path}",
                accion_tomada="request_denied",
            )

            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "message": "IP bloqueada por actividad sospechosa",
                },
            )

        # ----------------------------------------
        # registrar volumen de requests
        # ----------------------------------------
        rate_result = detector.record_request(ip)

        if rate_result == "rate_limit":
            self._save_security_event(
                ip=ip,
                tipo_evento="rate_limit",
                detalles=f"Alto volumen de requests detectado en path={request.url.path}",
                accion_tomada="flagged",
            )

        response = await call_next(request)

        # ----------------------------------------
        # detectar fuerza bruta por 401
        # ----------------------------------------
        if response.status_code == 401:
            auth_result = detector.record_401(ip)

            if auth_result == "too_many_401":
                self._save_security_event(
                    ip=ip,
                    tipo_evento="too_many_401",
                    detalles=f"Demasiados 401 detectados en path={request.url.path}",
                    accion_tomada="ip_blocked",
                )

        # ----------------------------------------
        # detectar escaneo de endpoints por 404
        # ----------------------------------------
        if response.status_code == 404:
            scan_result = detector.record_404(ip, request.url.path)

            if scan_result == "scanner_detected":
                self._save_security_event(
                    ip=ip,
                    tipo_evento="scanner_detected",
                    detalles=f"Escaneo detectado. Último endpoint: {request.url.path}",
                    accion_tomada="ip_blocked",
                )

        return response
