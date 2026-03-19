from __future__ import annotations

import json
import uuid
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)

        # Opcional: también lo mandamos en header para debugging
        response.headers["X-Request-ID"] = request_id

        # Solo intentamos inyectar en respuestas JSON “normales”
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            return response

        # Response puede venir como streaming; aquí cubrimos el caso más común:
        body = getattr(response, "body", None)
        if not body:
            return response

        try:
            obj = json.loads(body.decode("utf-8"))
        except Exception:
            return response

        # Si ya viene con formato estandar, inyectamos metadata.request_id
        if isinstance(obj, dict) and "success" in obj and "message" in obj and "data" in obj:
            metadata = obj.get("metadata") or {}
            if isinstance(metadata, dict):
                metadata["request_id"] = request_id
                obj["metadata"] = metadata

                return JSONResponse(
                    status_code=response.status_code,
                    content=obj,
                    headers=dict(response.headers),
                )

        return response
