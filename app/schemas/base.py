from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HateoasResponse(BaseModel):
    links: dict[str, Any] = Field(default_factory=dict, alias="_links")

    model_config = {
        "populate_by_name": True,
    }


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: T
    metadata: Optional[dict] = None
