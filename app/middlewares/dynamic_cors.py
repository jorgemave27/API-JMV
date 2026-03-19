from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.services.cors_service import cors_cache


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        allowed_origins = cors_cache.get_origins()

        if request.method == "OPTIONS" and origin:
            if origin not in allowed_origins:
                return PlainTextResponse("Disallowed CORS origin", status_code=400)

            response = PlainTextResponse("OK", status_code=200)
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Max-Age"] = "60"
            return response

        response = await call_next(request)

        if origin and origin in allowed_origins:
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response
