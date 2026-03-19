from __future__ import annotations

"""
Servicio para generar reporte de actividad de datos personales.

Este reporte puede entregarse al INAI en auditorías.

Incluye:
- total de usuarios
- usuarios activos
- usuarios anonimizados
- usuarios inactivos
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.usuario import Usuario


def generar_reporte_gdpr(db: Session) -> dict:
    """
    Genera métricas básicas de manejo de datos personales.
    """

    total_usuarios = db.query(func.count(Usuario.id)).scalar()

    usuarios_activos = db.query(func.count(Usuario.id)).filter(Usuario.activo == True).scalar()

    usuarios_inactivos = db.query(func.count(Usuario.id)).filter(Usuario.activo == False).scalar()

    usuarios_anonimizados = db.query(func.count(Usuario.id)).filter(Usuario.email.like("anon-%")).scalar()

    return {
        "total_usuarios": total_usuarios,
        "usuarios_activos": usuarios_activos,
        "usuarios_inactivos": usuarios_inactivos,
        "usuarios_anonimizados": usuarios_anonimizados,
    }
