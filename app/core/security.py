from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.api_key_manager import api_key_manager
from app.core.config import settings
from app.database.database import get_db
from app.models.usuario import Usuario


# -------------------------------------------------------------
# Contexto seguro para hashing de contraseñas con bcrypt
# -------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer auth para JWT
bearer_scheme = HTTPBearer(auto_error=False)

# -------------------------------------------------------------
# Configuración de seguridad
# -------------------------------------------------------------
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_BLOCK_MINUTES = 15
RESET_TOKEN_EXPIRE_HOURS = 1


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """
    Dependency de seguridad que valida la API Key enviada en el header.

    Regla:
    - acepta la key activa
    - acepta temporalmente la key anterior durante la ventana
      de convivencia posterior a una rotación
    """
    if not api_key_manager.is_valid_api_key(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
        )


def validate_password_complexity(password: str) -> None:
    """
    Valida complejidad mínima de contraseña.

    Reglas:
    - mínimo 8 caracteres
    - al menos 1 mayúscula
    - al menos 1 número
    - al menos 1 carácter especial
    """
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")

    if not re.search(r"[A-Z]", password):
        raise ValueError("La contraseña debe incluir al menos una mayúscula")

    if not re.search(r"\d", password):
        raise ValueError("La contraseña debe incluir al menos un número")

    if not re.search(r"[^\w\s]", password):
        raise ValueError("La contraseña debe incluir al menos un carácter especial")


def hash_password(password: str) -> str:
    """
    Genera el hash seguro de una contraseña en texto plano.
    """
    validate_password_complexity(password)
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si una contraseña en texto plano coincide con su hash.
    """
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    """
    Crea un JWT firmado con subject, tipo y expiración.
    """
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": subject,
        "type": token_type,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(subject: str) -> str:
    """
    Crea un access token de corta duración.
    """
    return _create_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str) -> str:
    """
    Crea un refresh token de larga duración.
    """
    return _create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """
    Decodifica y valida un JWT.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        ) from exc


def is_user_blocked(user: Usuario) -> bool:
    """
    Indica si la cuenta está bloqueada temporalmente.
    """
    return user.blocked_until is not None and user.blocked_until > datetime.utcnow()


def register_failed_login(db: Session, user: Usuario) -> None:
    """
    Registra un intento fallido de login y bloquea temporalmente
    si supera el límite permitido.
    """
    user.failed_login_attempts += 1

    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.blocked_until = datetime.utcnow() + timedelta(minutes=ACCOUNT_BLOCK_MINUTES)

    db.add(user)
    db.commit()
    db.refresh(user)


def reset_failed_login_attempts(db: Session, user: Usuario) -> None:
    """
    Reinicia contador de intentos fallidos tras login exitoso.
    """
    user.failed_login_attempts = 0
    user.blocked_until = None
    db.add(user)
    db.commit()
    db.refresh(user)


def generate_password_reset_token() -> str:
    """
    Genera token único de recuperación.
    """
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """
    Hashea el token de reset para no guardarlo en texto plano.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Obtiene el usuario autenticado desde el header:
        Authorization: Bearer <token>
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó token de autenticación",
        )

    token = credentials.credentials
    payload = decode_token(token)

    token_type = payload.get("type")
    subject = payload.get("sub")

    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un access token válido",
        )

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: subject ausente",
        )

    user = db.query(Usuario).filter(Usuario.email == subject).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo",
        )

    return user


def require_role(*roles: str):
    """
    Dependency factory para validar que el usuario autenticado
    tenga alguno de los roles permitidos.

    Ejemplo:
        Depends(require_role("admin"))
        Depends(require_role("admin", "editor"))
    """

    def role_checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permisos insuficientes. "
                    f"Rol requerido: {', '.join(roles)}. "
                    f"Rol actual: {current_user.rol}"
                ),
            )
        return current_user

    return role_checker