from fastapi import Header, HTTPException, status

API_KEY = "mi-clave-secreta"

def verificar_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
        )

