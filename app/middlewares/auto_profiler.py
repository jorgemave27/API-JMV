from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.performance.auto_profiler import auto_profiler_service

logger = logging.getLogger(__name__)


class AutoProfilerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:

        # ==============================
        # PROTECCIÓN TOTAL (TESTING / DEV)
        # ==============================
        if getattr(settings, "TESTING", False) or settings.APP_ENV != "production":
            return await call_next(request)

        try:
            # ==============================
            # 🔹 EJECUTAR REQUEST NORMAL
            # ==============================
            response: Response = await call_next(request)

        except Exception as e:
            # NUNCA romper request
            logger.error(f"[PROFILER] Error antes de response: {e}")
            return await call_next(request)

        # ==============================
        # SOLO GET
        # ==============================
        if request.method != "GET":
            return response

        try:
            candidate = getattr(request.app.state, "last_request_profile_candidate", None)
            if not candidate:
                return response

            path = candidate.get("path")
            consecutive_slow_requests = candidate.get("consecutive_slow_requests", 0)

            excluded_paths = {
                "/metrics",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/scalar",
            }

            if not path or path in excluded_paths:
                return response

            if path.startswith("/api/v1/admin/profile"):
                return response

            if consecutive_slow_requests < settings.PROFILING_CONSECUTIVE_SLOW_REQUESTS:
                return response

            # ==============================
            # EVITAR DUPLICADOS
            # ==============================
            if getattr(request.app.state, "profiler_running", False):
                return response

            request.app.state.profiler_running = True

            try:
                headers: dict[str, str] = {}

                auth_header = request.headers.get("Authorization")
                api_key = request.headers.get("X-API-Key")

                if auth_header:
                    headers["Authorization"] = auth_header
                if api_key:
                    headers["X-API-Key"] = api_key

                # ==============================
                # EJECUCIÓN SEGURA
                # ==============================
                report_path = await auto_profiler_service.profile_path(
                    app=request.app,
                    path=request.url.path + (f"?{request.url.query}" if request.url.query else ""),
                    headers=headers,
                )

                logger.warning(
                    "[PROFILER] Ejecutado | path=%s | report=%s",
                    path,
                    report_path,
                )

            except Exception as exc:
                # NO romper request
                logger.exception(
                    "[PROFILER] Error ejecutando profiler | path=%s | error=%s",
                    path,
                    exc,
                )

            finally:
                request.app.state.profiler_running = False

        except Exception as e:
            # fallback total
            logger.error(f"[PROFILER] Middleware error: {e}")

        return response