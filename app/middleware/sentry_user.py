from __future__ import annotations

import sentry_sdk
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SentryUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user = getattr(request.state, "user", None)

        if user:
            sentry_sdk.set_user(
                {
                    "id": getattr(user, "id", None),
                    "email": getattr(user, "email", None),
                }
            )

        response = await call_next(request)
        return response
