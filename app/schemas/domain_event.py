from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """
    Evento de dominio genérico para Event Sourcing / integración.

    Campos:
    - event_id: identificador único del evento
    - event_type: tipo de evento (ej. item.created)
    - aggregate_type: tipo de agregado (ej. item)
    - aggregate_id: id de la entidad afectada
    - occurred_at: fecha/hora UTC del evento
    - version: versión del schema del evento
    - payload: datos del evento
    - metadata: metadatos adicionales (usuario, origen, etc.)
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)