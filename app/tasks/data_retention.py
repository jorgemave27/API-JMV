from __future__ import annotations

"""
Retención automática de datos personales (GDPR / LFPDPPP)

Regla:
Usuarios inactivos por más de 3 años deben ser anonimizados
automáticamente para cumplir políticas de minimización
y retención de datos.

Este job puede ejecutarse con:
- Celery Beat
- Cron
- Scheduler interno
"""

import hashlib
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.usuario import Usuario

logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Configuración
# -------------------------------------------------------------

RETENTION_YEARS = 3


# -------------------------------------------------------------
# Utilidades de anonimización
# -------------------------------------------------------------


def _sha256(value: str) -> str:
    """
    Genera hash irreversible SHA256.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _anonimizar_email(email: str, usuario_id: int) -> str:
    """
    Mantiene formato de email válido
    pero elimina información personal.
    """
    digest = _sha256(email)
    return f"anon-{usuario_id}-{digest[:24]}@anon.local"


def _anonimizar_nombre(nombre: str | None, usuario_id: int) -> str:
    """
    Reemplaza nombre con hash irreversible.
    """
    base = nombre or f"user-{usuario_id}"
    digest = _sha256(base)
    return f"anon-{digest[:16]}"


def _anonimizar_rfc(rfc: str | None, usuario_id: int) -> str | None:
    """
    Anonimiza RFC.
    """
    if not rfc:
        return None

    digest = _sha256(f"{usuario_id}:{rfc}")
    return digest


# -------------------------------------------------------------
# Job principal
# -------------------------------------------------------------


def ejecutar_retencion_datos() -> None:
    """
    Busca usuarios inactivos por más de 3 años
    y anonimiza sus datos personales.
    """

    db: Session = SessionLocal()

    try:
        limite = datetime.utcnow() - timedelta(days=365 * RETENTION_YEARS)

        usuarios = (
            db.query(Usuario)
            .filter(
                Usuario.activo == True,
                Usuario.ultimo_acceso_at != None,
                Usuario.ultimo_acceso_at < limite,
            )
            .all()
        )

        if not usuarios:
            logger.info("RETENTION JOB | no usuarios para anonimizar")
            return

        for usuario in usuarios:
            email_original = usuario.email
            nombre_original = usuario.nombre
            rfc_original = usuario.rfc

            usuario.email = _anonimizar_email(usuario.email, usuario.id)
            usuario.nombre = _anonimizar_nombre(usuario.nombre, usuario.id)
            usuario.rfc = _anonimizar_rfc(usuario.rfc, usuario.id)

            usuario.activo = False
            usuario.updated_at = datetime.utcnow()

            logger.info(
                "RETENTION JOB | usuario=%s anonimizado | email=%s nombre=%s rfc=%s",
                usuario.id,
                email_original is not None,
                nombre_original is not None,
                rfc_original is not None,
            )

        db.commit()

        logger.info(
            "RETENTION JOB | completado | usuarios_anonimizados=%s",
            len(usuarios),
        )

    finally:
        db.close()
