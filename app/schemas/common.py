from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., examples=["VALIDATION_ERROR", "UNAUTHORIZED", "FORBIDDEN", "NOT_FOUND"])
    message: str = Field(..., examples=["Datos inválidos", "No autenticado", "No tienes permisos"])
    details: dict[str, Any] = Field(
        default_factory=dict,
        examples=[
            {"field": "price", "reason": "Debe ser mayor a 0"},
            {"missing_header": "Authorization"},
        ],
    )
    trace_id: str | None = Field(default=None, examples=["c5d59b94-304c-4cdc-a941-b8f69f7191fe"])


class ErrorResponse(BaseModel):
    error: ErrorDetail
