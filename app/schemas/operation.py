from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class OperationStatusResponse(BaseModel):
    """
    Respuesta para consultar el estado de una operación asíncrona CQRS.
    """
    operation_id: str
    status: Literal["pending", "completed", "failed"]
    resource_type: str
    resource_id: int | None = None
    event_type: str
    message: str
    created_at: datetime
    completed_at: datetime | None = None