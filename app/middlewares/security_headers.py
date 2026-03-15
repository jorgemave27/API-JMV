from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

MAX_BODY_SIZE = 1024 * 1024  # 1MB


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware de seguridad:
    - agrega headers de hardening
    - valida tamaño máximo de body
    """

    async def dispatch(self, request, call_next):
        # -------------------------------------------------
        # Bloqueo de payloads grandes
        # -------------------------------------------------
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                if int(content_length) > MAX_BODY_SIZE:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "success": False,
                            "message": "Payload Too Large",
                            "data": None,
                        },
                    )
            except ValueError:
                pass

        response = await call_next(request)

        # -------------------------------------------------
        # Headers de seguridad
        # -------------------------------------------------
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "object-src 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000"

        return response