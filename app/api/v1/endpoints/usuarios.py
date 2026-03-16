from __future__ import annotations

import hashlib
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_client_ip
from app.core.security import hash_password, verify_api_key, require_role
from app.database.database import get_db
from app.models.consentimiento_privacidad import ConsentimientoPrivacidad
from app.models.usuario import Usuario
from app.schemas.base import ApiResponse
from app.schemas.usuario import (
    UsuarioCreate,
    UsuarioDatosPersonalesRead,
    UsuarioRead,
    UsuarioRectificarRequest,
)

router = APIRouter()
logger = logging.getLogger(__name__)

PRIVACY_NOTICE_VERSION = "1.0"


def _get_usuario_or_404(
    db: Session,
    usuario_id: int,
) -> Usuario:
    """
    Obtiene un usuario o lanza 404 si no existe.
    """
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    return usuario


def _validar_acceso_usuario(
    usuario_id: int,
    current_user: Usuario,
) -> None:
    """
    Permite acceso si:
    - el usuario autenticado es admin
    - o el usuario autenticado es el dueño del recurso
    """
    if current_user.rol == "admin":
        return

    if current_user.id != usuario_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para acceder a los datos de otro usuario",
        )


def _sha256(value: str) -> str:
    """
    Hash SHA256 para anonimización irreversible.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _anonimizar_email(email: str, usuario_id: int) -> str:
    """
    Anonimiza email manteniendo formato válido y unicidad.
    """
    digest = _sha256(email)
    return f"anon-{usuario_id}-{digest[:24]}@anon.local"


def _anonimizar_nombre(nombre: str | None, usuario_id: int) -> str:
    """
    Anonimiza nombre con hash irreversible.
    """
    base = nombre or f"usuario-{usuario_id}"
    digest = _sha256(base)
    return f"anon-{digest[:16]}"


def _anonimizar_rfc(rfc: str | None, usuario_id: int) -> str | None:
    """
    Anonimiza RFC con hash irreversible.
    """
    if not rfc:
        return None

    digest = _sha256(f"{usuario_id}:{rfc}")
    return digest


@router.post(
    "/",
    response_model=UsuarioRead,
    summary="Registrar usuario",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin"))],
)
def registrar_usuario(
    payload: UsuarioCreate,
    db: Session = Depends(get_db),
    ip_cliente: str = Depends(get_client_ip),
):
    """
    Registra un usuario nuevo.

    Seguridad:
    - Hashea la contraseña antes de guardar
    - Nunca guarda la contraseña en texto plano
    - Registra consentimiento inicial de privacidad
    """
    existing = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario con ese email",
        )

    user = Usuario(
        nombre=payload.nombre,
        email=payload.email,
        rfc=payload.rfc,
        hashed_password=hash_password(payload.password),
        rol=payload.rol,
        activo=True,
    )

    db.add(user)
    db.flush()

    consentimiento = ConsentimientoPrivacidad(
        usuario_id=user.id,
        version_aviso=PRIVACY_NOTICE_VERSION,
        ip_cliente=ip_cliente,
    )
    db.add(consentimiento)

    db.commit()
    db.refresh(user)

    return user


@router.get(
    "/{usuario_id}/mis-datos",
    response_model=ApiResponse[UsuarioDatosPersonalesRead],
    summary="Obtener todos mis datos personales (ARCO - Acceso)",
    dependencies=[Depends(verify_api_key)],
)
def obtener_mis_datos(
    usuario_id: int,
    response: Response,
    db: Session = Depends(get_db),
    ip_cliente: str = Depends(get_client_ip),
    current_user: Usuario = Depends(require_role("admin", "editor", "lector")),
):
    """
    Derecho de ACCESO.

    Retorna todos los datos personales del usuario
    en formato JSON descargable.
    """
    _validar_acceso_usuario(usuario_id, current_user)

    usuario = _get_usuario_or_404(db, usuario_id)

    response.headers["Content-Disposition"] = (
        f'attachment; filename="usuario_{usuario_id}_mis_datos.json"'
    )

    data = UsuarioDatosPersonalesRead(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rfc=usuario.rfc,
        activo=usuario.activo,
        rol=usuario.rol,
        created_at=usuario.created_at,
        updated_at=usuario.updated_at,
        ultimo_acceso_at=usuario.ultimo_acceso_at,
        ip_cliente_actual=ip_cliente,
    )

    return ApiResponse[UsuarioDatosPersonalesRead](
        success=True,
        message="Datos personales obtenidos exitosamente",
        data=data,
        metadata={},
    )


@router.post(
    "/{usuario_id}/rectificar",
    response_model=ApiResponse[UsuarioDatosPersonalesRead],
    summary="Rectificar datos personales (ARCO - Rectificación)",
    dependencies=[Depends(verify_api_key)],
)
def rectificar_usuario(
    usuario_id: int,
    payload: UsuarioRectificarRequest,
    db: Session = Depends(get_db),
    ip_cliente: str = Depends(get_client_ip),
    current_user: Usuario = Depends(require_role("admin", "editor", "lector")),
):
    """
    Derecho de RECTIFICACIÓN.

    Permite corregir nombre, email y RFC
    con validación y registro en logs.
    """
    _validar_acceso_usuario(usuario_id, current_user)

    usuario = _get_usuario_or_404(db, usuario_id)

    cambios_realizados: dict[str, dict[str, str | None]] = {}

    # -------------------------------------------------------------
    # Rectificación de email
    # -------------------------------------------------------------
    if payload.email is not None and payload.email != usuario.email:
        email_duplicado = (
            db.query(Usuario)
            .filter(Usuario.email == payload.email, Usuario.id != usuario_id)
            .first()
        )
        if email_duplicado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un usuario con ese email",
            )

        cambios_realizados["email"] = {
            "anterior": usuario.email,
            "nuevo": payload.email,
        }
        usuario.email = payload.email

    # -------------------------------------------------------------
    # Rectificación de nombre
    # -------------------------------------------------------------
    if payload.nombre is not None and payload.nombre != usuario.nombre:
        cambios_realizados["nombre"] = {
            "anterior": usuario.nombre,
            "nuevo": payload.nombre,
        }
        usuario.nombre = payload.nombre

    # -------------------------------------------------------------
    # Rectificación de RFC
    # -------------------------------------------------------------
    if payload.rfc is not None and payload.rfc != usuario.rfc:
        cambios_realizados["rfc"] = {
            "anterior": usuario.rfc,
            "nuevo": payload.rfc,
        }
        usuario.rfc = payload.rfc

    if not cambios_realizados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hubo cambios para aplicar",
        )

    usuario.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(usuario)

    logger.info(
        "ARCO RECTIFICACION | usuario_objetivo=%s | usuario_solicitante=%s | ip=%s | cambios=%s",
        usuario.id,
        current_user.id,
        ip_cliente,
        list(cambios_realizados.keys()),
    )

    data = UsuarioDatosPersonalesRead(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        rfc=usuario.rfc,
        activo=usuario.activo,
        rol=usuario.rol,
        created_at=usuario.created_at,
        updated_at=usuario.updated_at,
        ultimo_acceso_at=usuario.ultimo_acceso_at,
        ip_cliente_actual=ip_cliente,
    )

    return ApiResponse[UsuarioDatosPersonalesRead](
        success=True,
        message="Datos personales rectificados exitosamente",
        data=data,
        metadata={
            "campos_actualizados": list(cambios_realizados.keys()),
        },
    )


@router.delete(
    "/{usuario_id}/cancelar",
    response_model=ApiResponse[dict],
    summary="Cancelar tratamiento de datos personales (ARCO - Cancelación)",
    dependencies=[Depends(verify_api_key)],
)
def cancelar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    ip_cliente: str = Depends(get_client_ip),
    current_user: Usuario = Depends(require_role("admin", "editor", "lector")),
):
    """
    Derecho de CANCELACIÓN.

    Anonimiza de forma irreversible:
    - nombre
    - email
    - RFC

    Conserva el registro para auditoría,
    pero ya sin datos personales reales.
    """
    _validar_acceso_usuario(usuario_id, current_user)

    usuario = _get_usuario_or_404(db, usuario_id)

    email_original = usuario.email
    nombre_original = usuario.nombre
    rfc_original = usuario.rfc

    usuario.nombre = _anonimizar_nombre(usuario.nombre, usuario.id)
    usuario.email = _anonimizar_email(usuario.email, usuario.id)
    usuario.rfc = _anonimizar_rfc(usuario.rfc, usuario.id)

    # Desactivar cuenta después de la cancelación.
    usuario.activo = False

    # Limpieza de estado sensible de autenticación.
    usuario.failed_login_attempts = 0
    usuario.blocked_until = None
    usuario.reset_token_hash = None
    usuario.reset_token_expires_at = None
    usuario.reset_token_used_at = None
    usuario.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(usuario)

    logger.info(
        "ARCO CANCELACION | usuario_objetivo=%s | usuario_solicitante=%s | ip=%s | email_anonimizado=%s | nombre_anonimizado=%s | rfc_anonimizado=%s",
        usuario.id,
        current_user.id,
        ip_cliente,
        email_original is not None,
        nombre_original is not None,
        rfc_original is not None,
    )

    return ApiResponse[dict](
        success=True,
        message="Datos personales anonimizados exitosamente",
        data={
            "ok": True,
            "usuario_id": usuario.id,
            "activo": usuario.activo,
            "anonimizado": True,
        },
        metadata={},
    )