from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.api_key_manager import api_key_manager
from app.core.config import settings
from app.database.database import get_db
from app.models.usuario import Usuario
from app.security.anomaly_detector import anomaly_detector
from app.security.token_blacklist import (
    blacklist_token,
    is_blacklisted,
    save_session,
    update_last_seen,
)

logger = logging.getLogger(__name__)


# =====================================================
# PASSWORD HASHING
# =====================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer auth para JWT
bearer_scheme = HTTPBearer(auto_error=False)


# =====================================================
# CONFIGURACIÓN SEGURIDAD
# =====================================================

MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_BLOCK_MINUTES = 15
RESET_TOKEN_EXPIRE_HOURS = 1


# =====================================================
# API KEY VALIDATION
# =====================================================


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """
    Valida API Key enviada en header.
    """

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
        )

    if settings.APP_ENV == "test":
        if x_api_key != settings.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key inválida",
            )
        return

    if x_api_key == settings.API_KEY:
        return

    try:
        if api_key_manager.is_valid_api_key(x_api_key):
            return
    except Exception:
        pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API Key inválida",
    )


# =====================================================
# PASSWORD SECURITY
# =====================================================


def validate_password_complexity(password: str) -> None:
    """
    Valida complejidad mínima de contraseña.
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
    Hashea contraseña en texto plano.
    """
    validate_password_complexity(password)
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica password en texto plano contra hash.
    """
    return pwd_context.verify(plain_password, hashed_password)


# =====================================================
# PASSWORD RESET TOKENS
# =====================================================


def generate_password_reset_token() -> str:
    """
    Genera token seguro para recuperación de contraseña.
    """
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """
    Hashea token de recuperación antes de guardarlo.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# =====================================================
# HELPERS DE REQUEST / TOKEN
# =====================================================


def get_request_ip(request: Request) -> str:
    """
    Obtiene IP real priorizando X-Forwarded-For.

    Orden:
    1. X-Forwarded-For
    2. request.client.host
    3. unknown
    """

    forwarded_for = request.headers.get("x-forwarded-for")

    if forwarded_for:
        # Puede venir una lista "ip1, ip2, ip3"
        real_ip = forwarded_for.split(",")[0].strip()
        if real_ip:
            return real_ip

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def get_request_user_agent(request: Request) -> str:
    """
    Obtiene user-agent del request.
    """
    return request.headers.get("user-agent", "unknown")


def get_token_remaining_seconds(payload: dict) -> int:
    """
    Calcula segundos restantes de vida de un JWT
    a partir del claim exp.
    """

    exp = payload.get("exp")

    if not exp:
        return 0

    try:
        remaining = int(float(exp) - datetime.now(timezone.utc).timestamp())
        return max(remaining, 0)
    except Exception:
        return 0


def register_session_from_token(
    *,
    token: str,
    user_id: int,
    request: Request,
) -> None:
    """
    Registra una sesión activa en Redis a partir de un JWT ya emitido.

    Se usa especialmente en:
    - login
    - refresh
    - validación normal de endpoints protegidos
    """

    try:
        payload = decode_token(token)
    except HTTPException:
        return

    jti = payload.get("jti")

    if not jti:
        return

    expires_in = get_token_remaining_seconds(payload)

    if expires_in <= 0:
        return

    ip = get_request_ip(request)
    user_agent = get_request_user_agent(request)

    save_session(
        jti=jti,
        user_id=user_id,
        ip=ip,
        user_agent=user_agent,
        expires_in=expires_in,
    )

    update_last_seen(jti)


# =====================================================
# JWT CREATION
# =====================================================


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    """
    Crea JWT con jti único.
    """

    expire = datetime.now(timezone.utc) + expires_delta
    jti = str(uuid.uuid4())

    payload = {
        "sub": subject,
        "type": token_type,
        "exp": expire,
        "jti": jti,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(subject: str) -> str:
    """
    Access token corto.
    """

    return _create_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str) -> str:
    """
    Refresh token largo.
    """

    return _create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


# =====================================================
# TOKEN DECODING
# =====================================================


def decode_token(token: str) -> dict:
    """
    Decodifica JWT.
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


# =====================================================
# ACCOUNT SECURITY
# =====================================================


def is_user_blocked(user: Usuario) -> bool:
    """
    Indica si la cuenta está temporalmente bloqueada.
    """
    return user.blocked_until is not None and user.blocked_until > datetime.utcnow()


def register_failed_login(db: Session, user: Usuario) -> None:
    """
    Registra intento fallido de login.
    """

    user.failed_login_attempts += 1

    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.blocked_until = datetime.utcnow() + timedelta(minutes=ACCOUNT_BLOCK_MINUTES)

    db.add(user)
    db.commit()
    db.refresh(user)


def reset_failed_login_attempts(db: Session, user: Usuario) -> None:
    """
    Reinicia contador de fallos al autenticar correctamente.
    """

    user.failed_login_attempts = 0
    user.blocked_until = None

    db.add(user)
    db.commit()
    db.refresh(user)


# =====================================================
# CURRENT USER
# =====================================================


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Obtiene usuario autenticado validando:
    - JWT
    - blacklist
    - token theft
    - sesiones distribuidas
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
    jti = payload.get("jti")

    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token requerido",
        )

    if jti and is_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revocado",
        )

    user = db.query(Usuario).filter(Usuario.email == subject).first()

    if not user or not user.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inválido",
        )

    ip = get_request_ip(request)

    # =====================================================
    # TOKEN THEFT DETECTION
    # =====================================================

    if jti and anomaly_detector.detect_token_theft(jti, ip):
        logger.warning(
            "SECURITY_EVENT posible_robo_token user=%s jti=%s ip=%s",
            user.email,
            jti,
            ip,
        )

        blacklist_token(
            jti,
            get_token_remaining_seconds(payload),
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida. Reautenticación requerida",
        )

    # =====================================================
    # SESSION TRACKING
    # =====================================================

    if jti:
        register_session_from_token(
            token=token,
            user_id=user.id,
            request=request,
        )

    return user


# =====================================================
# ROLE AUTHORIZATION
# =====================================================


def require_role(*roles: str):
    """
    Valida rol del usuario autenticado.
    """

    def role_checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )

        return current_user

    return role_checker
