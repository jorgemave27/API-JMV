from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import (
    RESET_TOKEN_EXPIRE_HOURS,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_password_reset_token,
    get_current_user,
    get_token_remaining_seconds,
    hash_password,
    hash_reset_token,
    is_user_blocked,
    register_failed_login,
    register_session_from_token,
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
from app.security.token_blacklist import (
    blacklist_token,
    close_session,
    get_user_sessions,
    revoke_all_user_tokens,
)

router = APIRouter()

# Bearer explícito para endpoints que trabajan directo con token actual
bearer_scheme = HTTPBearer()


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login de usuario con JWT",
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Autentica usuario y registra la sesión activa desde el momento del login.
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
            detail="Cuenta bloqueada temporalmente",
        )

    if not verify_password(payload.password, user.hashed_password):
        register_failed_login(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    reset_failed_login_attempts(db, user)

    access_token = create_access_token(user.email)
    refresh_token = create_refresh_token(user.email)

    # -------------------------------------------------
    # Registrar sesión activa del access token desde login
    # Esto permite revocar todos los tokens al cambiar password,
    # incluso si el usuario aún no ha llamado otro endpoint protegido.
    # -------------------------------------------------
    register_session_from_token(
        token=access_token,
        user_id=user.id,
        request=request,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",  # nosec
    )


# ---------------------------------------------------------
# REFRESH TOKEN
# ---------------------------------------------------------
@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token con refresh token",
)
def refresh_token(
    payload: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Recibe refresh token válido y emite nuevo access token,
    registrando también la nueva sesión activa.
    """

    token_payload = decode_token(payload.refresh_token)

    token_type = token_payload.get("type")
    subject = token_payload.get("sub")

    if token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere refresh token",
        )

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )

    user = db.query(Usuario).filter(Usuario.email == subject).first()

    if user is None or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no válido",
        )

    new_access_token = create_access_token(user.email)

    # -------------------------------------------------
    # Registrar nueva sesión del access token renovado
    # -------------------------------------------------
    register_session_from_token(
        token=new_access_token,
        user_id=user.id,
        request=request,
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=payload.refresh_token,
        token_type="bearer",  # nosec
    )


# ---------------------------------------------------------
# LOGOUT (TOKEN BLACKLIST)
# ---------------------------------------------------------
@router.post(
    "/logout",
    summary="Cerrar sesión",
)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    Revoca el token actual usando blacklist.
    """

    token = credentials.credentials
    payload = decode_token(token)

    jti = payload.get("jti")

    if not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido",
        )

    expires_in = get_token_remaining_seconds(payload)

    blacklist_token(jti, expires_in)

    return {
        "success": True,
        "message": "Sesión cerrada correctamente",
        "data": None,
        "metadata": {},
    }


# ---------------------------------------------------------
# LISTAR SESIONES ACTIVAS
# ---------------------------------------------------------
@router.get(
    "/sesiones",
    summary="Listar sesiones activas",
)
def listar_sesiones(
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista sesiones activas del usuario autenticado.
    """

    sesiones = get_user_sessions(current_user.id)

    return {
        "success": True,
        "message": "Sesiones activas",
        "data": sesiones,
        "metadata": {
            "total": len(sesiones),
        },
    }


# ---------------------------------------------------------
# CERRAR SESIÓN REMOTA
# ---------------------------------------------------------
@router.post(
    "/cerrar-sesion/{jti}",
    summary="Cerrar una sesión específica",
)
def cerrar_sesion_remota(
    jti: str,
    current_user: Usuario = Depends(get_current_user),
):
    """
    Cierra una sesión remota específica usando su jti.
    """

    close_session(jti)

    return {
        "success": True,
        "message": "Sesión cerrada",
        "data": None,
        "metadata": {},
    }


# ---------------------------------------------------------
# CAMBIAR PASSWORD
# ---------------------------------------------------------
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
    Cambia contraseña y revoca todas las sesiones activas
    registradas del usuario.
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

    # -------------------------------------------------
    # Revocar todos los tokens activos del usuario
    # -------------------------------------------------
    revoke_all_user_tokens(current_user.id)

    return {
        "success": True,
        "message": "Contraseña actualizada exitosamente",
        "data": None,
        "metadata": {},
    }


# ---------------------------------------------------------
# FORGOT PASSWORD
# ---------------------------------------------------------
@router.post(
    "/forgot-password",
    summary="Solicitar recuperación de contraseña",
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Genera token de recuperación temporal.
    Por ahora solo se imprime para pruebas/local.
    """

    user = db.query(Usuario).filter(Usuario.email == payload.email).first()

    generic_response = {
        "success": True,
        "message": "Si el email existe se enviaron instrucciones",
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


# ---------------------------------------------------------
# RESET PASSWORD
# ---------------------------------------------------------
@router.post(
    "/reset-password",
    summary="Restablecer contraseña con token",
)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Restablece contraseña usando token único temporal.
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

    # -------------------------------------------------
    # Revocar sesiones activas existentes tras reset
    # -------------------------------------------------
    revoke_all_user_tokens(user.id)

    return {
        "success": True,
        "message": "Contraseña restablecida exitosamente",
        "data": None,
        "metadata": {},
    }
