from __future__ import annotations

import sys
from collections.abc import AsyncGenerator
from pathlib import Path

# -------------------------------------------------------------
# Añadimos el root del proyecto al PYTHONPATH
# Esto permite importar módulos como:
# from app.core.security import ...
# -------------------------------------------------------------
sys.path.append(str(Path(__file__).resolve().parents[1]))

import random
import string
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.database.database import Base, get_db, get_db_async
from app.main import app
from app.models.usuario import Usuario

# -------------------------------------------------------------
# Constantes globales usadas por los tests
# -------------------------------------------------------------
API_KEY = "dev-secret-key-change-me"
API_PREFIX = "/api/v1"
ITEMS_BASE = f"{API_PREFIX}/items"

# -------------------------------------------------------------
# Contraseñas válidas para tests
# (deben cumplir la política de seguridad)
# -------------------------------------------------------------
TEST_ADMIN_PASSWORD = "Test123!"
TEST_EDITOR_PASSWORD = "Test123!"
TEST_LECTOR_PASSWORD = "Test123!"


# -------------------------------------------------------------
# Generador de SKU aleatorio para evitar colisiones
# -------------------------------------------------------------
def rand_sku(prefix: str = "CAJA") -> str:
    """
    Genera un SKU aleatorio para evitar colisiones en tests.
    """
    return f"{prefix}-{''.join(random.choices(string.digits, k=6))}"


# -------------------------------------------------------------
# Convierte URL sync a async para SQLAlchemy async
# -------------------------------------------------------------
def build_async_test_database_url(database_url: str) -> str:
    """
    Convierte una URL sync a async para usar AsyncSession en tests.
    """
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

    return database_url


# =============================================================
# Fixture principal de base de datos
# =============================================================
@pytest.fixture(scope="function")
def setup_db(tmp_path: Path):
    """
    Crea una base de datos limpia para cada test.

    Qué hace:
    - crea SQLite temporal
    - crea engine sync
    - crea engine async
    - override de dependencias FastAPI
    - desactiva cache
    """

    test_db_path = tmp_path / "test.db"
    test_db_url = f"sqlite:///{test_db_path}"
    async_test_db_url = build_async_test_database_url(test_db_url)

    # ---------------------------------------------------------
    # Engine síncrono
    # ---------------------------------------------------------
    engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    # Crear esquema limpio
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # ---------------------------------------------------------
    # Engine asíncrono
    # ---------------------------------------------------------
    async_engine = create_async_engine(
        async_test_db_url,
        connect_args={"check_same_thread": False},
    )

    AsyncTestingSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # ---------------------------------------------------------
    # Overrides de dependencias FastAPI
    # ---------------------------------------------------------
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def override_get_db_async() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncTestingSessionLocal() as db:
            yield db

    # ---------------------------------------------------------
    # Desactivar cache durante tests
    # ---------------------------------------------------------
    original_cache_enabled = settings.CACHE_ENABLED
    settings.CACHE_ENABLED = False

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_async] = override_get_db_async

    yield TestingSessionLocal

    # ---------------------------------------------------------
    # Limpieza después del test
    # ---------------------------------------------------------
    app.dependency_overrides.clear()
    settings.CACHE_ENABLED = original_cache_enabled

    # IMPORTANTE:
    # cerrar correctamente engines para evitar warnings
    import asyncio

    engine.dispose()
    asyncio.run(async_engine.dispose())


# =============================================================
# Cliente HTTP de pruebas
# =============================================================
@pytest.fixture(scope="function")
def client(setup_db):
    """
    Cliente FastAPI usado para tests de integración.
    """
    with TestClient(app) as c:
        yield c


# =============================================================
# Sesión DB directa
# =============================================================
@pytest.fixture(scope="function")
def db_session(setup_db):
    """
    Permite consultar DB directamente dentro del test.
    """
    db = setup_db()
    try:
        yield db
    finally:
        db.close()


# =============================================================
# Helper para crear usuarios
# =============================================================
def _ensure_user(
    TestingSessionLocal,
    *,
    email: str,
    password: str,
    rol: str,
) -> str:
    """
    Crea o actualiza un usuario de prueba.

    Retorna un access token JWT listo para usar.
    """
    db = TestingSessionLocal()

    try:
        user = db.query(Usuario).filter(Usuario.email == email).first()

        if user is None:
            user = Usuario(
                email=email,
                hashed_password=hash_password(password),
                activo=True,
                rol=rol,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        else:
            user.hashed_password = hash_password(password)
            user.activo = True
            user.rol = rol
            user.failed_login_attempts = 0
            user.blocked_until = None
            user.reset_token_hash = None
            user.reset_token_expires_at = None
            user.reset_token_used_at = None

            db.commit()
            db.refresh(user)

        token = create_access_token(user.email)
        return token

    finally:
        db.close()


# =============================================================
# Headers reutilizables por rol
# =============================================================
@pytest.fixture()
def auth_headers(setup_db) -> dict[str, str]:
    """
    Headers estándar para escritura (rol editor).
    """
    token = _ensure_user(
        setup_db,
        email="editor@test.com",
        password=TEST_EDITOR_PASSWORD,
        rol="editor",
    )

    return {
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture()
def admin_auth_headers(setup_db) -> dict[str, str]:
    """
    Headers de administrador.
    """
    token = _ensure_user(
        setup_db,
        email="admin@test.com",
        password=TEST_ADMIN_PASSWORD,
        rol="admin",
    )

    return {
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture()
def lector_auth_headers(setup_db) -> dict[str, str]:
    """
    Headers de rol lector.
    """
    token = _ensure_user(
        setup_db,
        email="lector@test.com",
        password=TEST_LECTOR_PASSWORD,
        rol="lector",
    )

    return {
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {token}",
    }


# =============================================================
# Fixtures para integración E2E
# =============================================================
@pytest.fixture()
def usuario_admin(admin_auth_headers) -> dict[str, Any]:
    token = admin_auth_headers["Authorization"].replace("Bearer ", "")

    return {
        "token": token,
        "headers": admin_auth_headers,
        "rol": "admin",
    }


@pytest.fixture()
def usuario_lector(lector_auth_headers) -> dict[str, Any]:
    token = lector_auth_headers["Authorization"].replace("Bearer ", "")

    return {
        "token": token,
        "headers": lector_auth_headers,
        "rol": "lector",
    }


# =============================================================
# Helpers de validación
# =============================================================
def unwrap(resp_json: dict) -> dict:
    """
    Valida wrapper ApiResponse.
    """
    assert isinstance(resp_json, dict)
    assert "success" in resp_json
    assert "message" in resp_json
    assert "data" in resp_json
    assert "metadata" in resp_json

    return resp_json


def request_id_from(resp) -> str:
    """
    Valida header x-request-id.
    """
    rid = resp.headers.get("x-request-id")

    assert rid is not None
    assert len(rid) > 0

    return rid


# =============================================================
# Helpers para items
# =============================================================
def create_item(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    name: str,
    price: float,
    stock: int,
    sku_prefix: str = "T",
    codigo_sku: str = "AB-1234",
    categoria_id: int | None = None,
) -> dict[str, Any]:

    payload = {
        "name": name,
        "description": "para test",
        "price": price,
        "sku": rand_sku(sku_prefix),
        "codigo_sku": codigo_sku,
        "stock": stock,
    }

    if categoria_id is not None:
        payload["categoria_id"] = categoria_id

    r = client.post(
        f"{ITEMS_BASE}/",
        headers=auth_headers,
        json=payload,
    )

    assert r.status_code in (200, 201), r.text

    request_id_from(r)

    body = unwrap(r.json())

    assert body["success"] is True
    assert isinstance(body["data"], dict)

    return body["data"]

def get_items_wrapped(client: TestClient, auth_headers: dict[str, str], query: str = "") -> dict:
    """
    Obtiene listado de items y valida wrapper estándar.
    """
    url = f"{ITEMS_BASE}/" + (f"?{query}" if query else "")

    r = client.get(url, headers=auth_headers)

    assert r.status_code == 200, r.text
    request_id_from(r)

    body = unwrap(r.json())

    assert body["success"] is True
    assert isinstance(body["data"], dict)
    assert "items" in body["data"]

    return body


def get_deleted_wrapped(client: TestClient, auth_headers: dict[str, str], query: str = "") -> dict:
    """
    Obtiene listado de items eliminados y valida wrapper estándar.
    """
    url = f"{ITEMS_BASE}/eliminados" + (f"?{query}" if query else "")

    r = client.get(url, headers=auth_headers)

    assert r.status_code == 200, r.text
    request_id_from(r)

    body = unwrap(r.json())

    assert body["success"] is True
    assert isinstance(body["data"], dict)
    assert "items" in body["data"]

    return body