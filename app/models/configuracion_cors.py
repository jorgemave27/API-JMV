from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ConfiguracionCors(Base):
    __tablename__ = "configuracion_cors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    origin: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    activo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())