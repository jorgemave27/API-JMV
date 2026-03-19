from __future__ import annotations

import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.saga_log import SagaLog
from app.saga.constants import SagaStatus


class SagaRepository:
    """
    Repositorio para registrar y consultar pasos de saga.

    La idempotencia se basa en:
    - unique constraint (saga_id, step)
    - consulta previa antes de ejecutar el efecto del mensaje
    """

    def __init__(self, db: Session):
        self.db = db

    def get_step(self, saga_id: str, step: str) -> SagaLog | None:
        return (
            self.db.query(SagaLog)
            .filter(SagaLog.saga_id == saga_id, SagaLog.step == step)
            .first()
        )

    def already_processed(self, saga_id: str, step: str) -> bool:
        """
        Indica si un paso ya fue registrado y, por tanto,
        no debe procesarse otra vez.
        """
        existing = self.get_step(saga_id, step)
        return existing is not None

    def create_step(self, saga_id: str, step: str, payload: dict) -> SagaLog:
        """
        Crea el registro inicial del paso.

        Si el paso ya existe por reentrega de RabbitMQ, se hace rollback
        y se devuelve el registro existente.
        """
        log = SagaLog(
            saga_id=saga_id,
            step=step,
            status=SagaStatus.PENDING,
            payload=json.dumps(payload, default=str),
        )

        try:
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
            return log
        except IntegrityError:
            self.db.rollback()
            existing = self.get_step(saga_id, step)
            if existing is None:
                raise
            return existing

    def update_status(
        self,
        saga_id: str,
        step: str,
        status: str,
        error: str | None = None,
    ) -> None:
        log = self.get_step(saga_id, step)
        if not log:
            return

        log.status = status
        if error is not None:
            log.error = error

        self.db.commit()