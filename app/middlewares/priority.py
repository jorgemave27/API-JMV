from starlette.middleware.base import BaseHTTPMiddleware


class PriorityMiddleware(BaseHTTPMiddleware):
    """
    Requests a /priority/* bypass backpressure
    """

    async def dispatch(self, request, call_next):
        request.state.is_priority = request.url.path.startswith("/priority")
        return await call_next(request)