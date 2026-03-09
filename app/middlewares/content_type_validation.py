from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """
    Valida Content-Type para requests mutables que realmente envían body.

    Regla:
    - POST / PUT / PATCH con body deben enviar application/json
    - POST sin body (ej. /items/{id}/restaurar) no deben bloquearse
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in {"POST", "PUT", "PATCH"}:
            content_length = request.headers.get("content-length")
            transfer_encoding = request.headers.get("transfer-encoding", "").lower()

            has_body = (
                (content_length is not None and content_length != "0")
                or "chunked" in transfer_encoding
            )

            if has_body:
                content_type = request.headers.get("content-type", "").lower()

                if "application/json" not in content_type:
                    return JSONResponse(
                        status_code=415,
                        content={
                            "success": False,
                            "message": "Content-Type inválido. Debe ser application/json",
                            "data": None,
                            "metadata": {},
                        },
                    )

        return await call_next(request)