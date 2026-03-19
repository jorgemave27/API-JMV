from __future__ import annotations

from typing import Any, Optional

from fastapi.responses import JSONResponse

from app.schemas.base import ApiResponse


def error_response(
    *,
    status_code: int,
    message: str,
    data: Any = None,
    metadata: Optional[dict] = None,
) -> JSONResponse:
    """
    Respuesta de error estandarizada:
    {
      success: false,
      message: "...",
      data: null | {...},
      metadata: {...}
    }
    """
    payload = ApiResponse[Any](
        success=False,
        message=message,
        data=data,
        metadata=metadata,
    ).model_dump()

    return JSONResponse(status_code=status_code, content=payload)
