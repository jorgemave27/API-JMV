# Ruta: auth-service/app/api/routes/internal.py

from fastapi import APIRouter, Header, HTTPException, Response
from jose import JWTError, jwt

router = APIRouter()

# En esta tarea dejamos el secret fijo para empatar con docker-compose.
# Después se puede mover a settings.
SECRET_KEY = "super-secret-key-change-me-in-production"
ALGORITHM = "HS256"


@router.get("/verify-token")
def verify_token(
    response: Response,
    authorization: str | None = Header(default=None),
):
    """
    Endpoint interno consumido por NGINX vía auth_request.

    IMPORTANTE:
    - NGINX auth_request usa GET por defecto.
    - Por eso este endpoint DEBE aceptar GET.
    - Si el JWT es válido, regresamos 200 y mandamos el identificador
      del usuario en el header X-User-Id.
    - En tu sistema actual el claim "sub" contiene el email del usuario,
      no el id numérico. Por eso aquí propagamos el email.
    """

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token inválido o ausente")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Token inválido o expirado") from exc

    subject = payload.get("sub")
    token_type = payload.get("type")

    if not subject:
        raise HTTPException(status_code=401, detail="Token sin subject")

    if token_type != "access":
        raise HTTPException(status_code=401, detail="Access token requerido")

    # OJO:
    # En tu implementación actual "sub" = email, no user_id numérico.
    # Conservamos el nombre del header para no tocar más NGINX,
    # pero el valor real que viaja es el email.
    response.headers["X-User-Id"] = str(subject)

    return {"valid": True}