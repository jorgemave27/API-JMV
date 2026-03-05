from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import settings


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """
    Dependency de seguridad que valida la API Key enviada en el header.

    Header esperado:
        X-API-Key: <api_key>

    Si la API Key no existe o no coincide con la configurada
    en variables de entorno, se lanza HTTP 401.
    """

    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
        )