from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.repositories.item_repository import ItemRepository

API_KEY = "mi-clave-secreta"


def verificar_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """
    Verifica que la API Key enviada en el header sea válida.
    """
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
        )


def get_item_repo(db: Session = Depends(get_db)) -> ItemRepository:
    """
    Dependencia FastAPI para inyectar el repository de Items.
    """
    return ItemRepository(db)
