from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_api_key, require_role
from app.database.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioRead

router = APIRouter()


@router.post(
    "/",
    response_model=UsuarioRead,
    summary="Registrar usuario",
    dependencies=[Depends(verify_api_key), Depends(require_role("admin"))],
)
def registrar_usuario(
    payload: UsuarioCreate,
    db: Session = Depends(get_db),
):
    """
    Registra un usuario nuevo.

    Seguridad:
    - Hashea la contraseña antes de guardar
    - Nunca guarda la contraseña en texto plano
    """
    existing = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario con ese email",
        )

    user = Usuario(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        rol=payload.rol,
        activo=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user