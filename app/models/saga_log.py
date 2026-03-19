from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from app.database.database import Base


class SagaLog(Base):
    """
    Registro de pasos de saga.

    Sirve para:
    - trazabilidad
    - idempotencia
    - debugging
    - auditoría de compensaciones

    status permitidos:
    - PENDING
    - COMPLETED
    - FAILED
    - COMPENSATING
    - COMPENSATED
    """

    __tablename__ = "saga_log"

    __table_args__ = (
        UniqueConstraint("saga_id", "step", name="uq_saga_log_saga_id_step"),
    )

    id = Column(Integer, primary_key=True, index=True)

    saga_id = Column(String(100), nullable=False, index=True)
    step = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="PENDING", index=True)

    # JSON serializado como texto para no meter dependencias extra
    payload = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )