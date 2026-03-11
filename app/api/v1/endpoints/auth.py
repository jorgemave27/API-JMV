from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    ACCOUNT_BLOCK_MINUTES,
    RESET_TOKEN_EXPIRE_HOURS,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    get_current_user,
    hash_password,
    hash_reset_token,
    is_user_blocked,
    register_failed_login,
    reset_failed_login_attempts,
    verify_password,
)
from app.database.database import get_db
from app.models.usuario import Usuario
from app.schemas.auth import (
    CambiarPasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
)

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login de usuario con JWT",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Autentica un usuario por email y password y retorna access/refresh tokens.

    Seguridad adicional:
    - Bloqueo temporal después de múltiples intentos fallidos
    """
    user = db.query(Usuario).filter(Usuario.email == payload.email).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo",
        )

    if is_user_blocked(user):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=(
                "Cuenta bloqueada temporalmente. "
                "Intenta de nuevo más tarde."
            ),
        )

    if not verify_password(payload.password, user.hashed_password):
        register_failed_login(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    reset_failed_login_attempts(db, user)

    return TokenResponse(
        access_token=create_access_token(user.email),
        refresh_token=create_refresh_token(user.email),
        token_type="bearer",  # nosec B106
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token con refresh token",
)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """
    Recibe un refresh token válido y devuelve un nuevo access token.
    """
    token_payload = decode_token(payload.refresh_token)

    token_type = token_payload.get("type")
    subject = token_payload.get("sub")

    if token_type != "refresh":  # nosec B105
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un refresh token válido",
        )

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: subject ausente",
        )

    user = db.query(Usuario).filter(Usuario.email == subject).first()

    if user is None or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no válido para refrescar token",
        )

    return TokenResponse(
        access_token=create_access_token(user.email),
        refresh_token=payload.refresh_token,
        token_type="bearer",  # nosec B106
    )


@router.post(
    "/cambiar-password",
    summary="Cambiar contraseña autenticado",
)
def cambiar_password(
    payload: CambiarPasswordRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Cambia la contraseña del usuario autenticado
    requiriendo la contraseña actual.
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "message": "Contraseña actualizada exitosamente",
        "data": None,
        "metadata": {},
    }


@router.post(
    "/forgot-password",
    summary="Solicitar recuperación de contraseña",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Genera token de recuperación de un solo uso con expiración controlada.

    Por ahora:
    - no envía email real
    - solo imprime el token para pruebas/local
    """
    user = db.query(Usuario).filter(Usuario.email == payload.email).first()

    # Respuesta genérica para no filtrar si el usuario existe o no
    generic_response = {
        "success": True,
        "message": "Si el email existe, se enviaron instrucciones de recuperación",
        "data": None,
        "metadata": {},
    }

    if user is None or not user.activo:
        return generic_response

    raw_token = generate_password_reset_token()

    user.reset_token_hash = hash_reset_token(raw_token)
    user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)
    user.reset_token_used_at = None

    db.add(user)
    db.commit()
    db.refresh(user)

    print(f"[RESET PASSWORD] email={user.email} token={raw_token}")

    return generic_response


@router.post(
    "/reset-password",
    summary="Restablecer contraseña con token",
)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Usa un token único y temporal para establecer una nueva contraseña.
    """
    token_hash = hash_reset_token(payload.token)

    user = db.query(Usuario).filter(Usuario.reset_token_hash == token_hash).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    if user.reset_token_used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    if user.reset_token_expires_at is None or user.reset_token_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )

    user.hashed_password = hash_password(payload.new_password)
    user.reset_token_used_at = datetime.utcnow()
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.failed_login_attempts = 0
    user.blocked_until = None

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": "Contraseña restablecida exitosamente",
        "data": None,
        "metadata": {},
    }