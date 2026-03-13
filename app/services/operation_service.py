from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class OperationService:
    """
    Gestiona el estado de operaciones CQRS.
    Si Redis falla, no rompe la app ni los tests.
    """

    def __init__(self) -> None:
        self.redis_client = None
        try:
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            self.redis_client.ping()
        except Exception as exc:
            logger.warning("Redis no disponible para OperationService: %s", exc)
            self.redis_client = None

    def create_operation(self, resource_type: str, event_type: str, resource_id: int | None = None) -> str:
        operation_id = str(uuid.uuid4())

        if not self.redis_client:
            return operation_id

        payload = {
            "operation_id": operation_id,
            "status": "pending",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "event_type": event_type,
            "message": "Operación aceptada. Esperando actualización del modelo de lectura.",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }

        try:
            self.redis_client.setex(f"operation:{operation_id}", 3600, json.dumps(payload))
        except Exception as exc:
            logger.warning("No se pudo guardar operación en Redis: %s", exc)

        return operation_id

    def complete_operation(self, operation_id: str, resource_id: int | None = None) -> None:
        if not self.redis_client:
            return

        try:
            key = f"operation:{operation_id}"
            raw = self.redis_client.get(key)
            if not raw:
                return

            payload = json.loads(raw)
            payload["status"] = "completed"
            payload["resource_id"] = resource_id
            payload["message"] = "Modelo de lectura actualizado."
            payload["completed_at"] = datetime.now(timezone.utc).isoformat()
            self.redis_client.setex(key, 3600, json.dumps(payload))
        except Exception as exc:
            logger.warning("No se pudo completar operación en Redis: %s", exc)

    def fail_operation(self, operation_id: str, message: str) -> None:
        if not self.redis_client:
            return

        try:
            key = f"operation:{operation_id}"
            raw = self.redis_client.get(key)
            if not raw:
                return

            payload = json.loads(raw)
            payload["status"] = "failed"
            payload["message"] = message
            payload["completed_at"] = datetime.now(timezone.utc).isoformat()
            self.redis_client.setex(key, 3600, json.dumps(payload))
        except Exception as exc:
            logger.warning("No se pudo marcar operación fallida en Redis: %s", exc)

    def get_operation(self, operation_id: str) -> dict[str, Any] | None:
        if not self.redis_client:
            return {
                "operation_id": operation_id,
                "status": "pending",
                "resource_type": "item",
                "resource_id": None,
                "event_type": "unknown",
                "message": "Redis no disponible. Estado no persistido.",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
            }

        try:
            raw = self.redis_client.get(f"operation:{operation_id}")
            if not raw:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("No se pudo consultar operación en Redis: %s", exc)
            return None