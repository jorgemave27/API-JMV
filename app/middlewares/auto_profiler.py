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
        response = await call_next(request)

        if settings.APP_ENV != "development":
            return response

        if request.method != "GET":
            return response

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

        if path in excluded_paths:
            return response

        if path.startswith("/api/v1/admin/profile"):
            return response

        if consecutive_slow_requests < settings.PROFILING_CONSECUTIVE_SLOW_REQUESTS:
            return response

        try:
            headers: dict[str, str] = {}
            auth_header = request.headers.get("Authorization")
            api_key = request.headers.get("X-API-Key")

            if auth_header:
                headers["Authorization"] = auth_header
            if api_key:
                headers["X-API-Key"] = api_key

            report_path = await auto_profiler_service.profile_path(
                app=request.app,
                path=request.url.path + (f"?{request.url.query}" if request.url.query else ""),
                headers=headers,
            )

            logger.warning(
                "Auto profiling ejecutado | path=%s | report_path=%s",
                path,
                report_path,
            )

        except Exception as exc:
            logger.exception(
                "Error ejecutando auto profiler | path=%s | error=%s",
                path,
                exc,
            )

        return response