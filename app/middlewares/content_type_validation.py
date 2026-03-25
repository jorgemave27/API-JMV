from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class ContentTypeValidationMiddleware(BaseHTTPMiddleware):
    """
    🔥 Content-Type Validation Middleware (VERSIÓN FINAL PRO)

    Qué hace:
    - Valida Content-Type SOLO cuando realmente hay body
    - Permite:
        ✔ application/json (APIs normales)
        ✔ multipart/form-data (uploads de archivos)
    - No rompe endpoints sin body
    - No rompe uploads (este era tu bug)

    🔥 IMPORTANTE:
    - NO valida GET / DELETE
    - NO bloquea si no hay body
    """

    async def dispatch(self, request: Request, call_next) -> Response:

        # ==============================
        # SOLO MÉTODOS CON POSIBLE BODY
        # ==============================
        if request.method in {"POST", "PUT", "PATCH"}:

            content_length = request.headers.get("content-length")
            transfer_encoding = request.headers.get("transfer-encoding", "").lower()

            # Detectar si realmente hay body
            has_body = (
                (content_length is not None and content_length != "0")
                or "chunked" in transfer_encoding
            )

            # ==============================
            # VALIDAR SOLO SI HAY BODY
            # ==============================
            if has_body:
                content_type = request.headers.get("content-type", "").lower()

                # 🔥 FIX CRÍTICO:
                # - Acepta JSON
                # - Acepta multipart (file uploads)
                # - Maneja casos como multipart/form-data; boundary=...
                is_json = "application/json" in content_type
                is_multipart = "multipart/form-data" in content_type

                if not (is_json or is_multipart):
                    return JSONResponse(
                        status_code=415,
                        content={
                            "success": False,
                            "message": "Content-Type inválido. Usa application/json o multipart/form-data",
                            "data": None,
                            "metadata": {},
                        },
                    )

        # ==============================
        # CONTINUAR REQUEST NORMAL
        # ==============================
        return await call_next(request)