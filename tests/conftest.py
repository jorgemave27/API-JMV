from __future__ import annotations

import sys
from pathlib import Path

# Root del proyecto al path (para imports app.*)
sys.path.append(str(Path(__file__).resolve().parents[1]))

import random
import string
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.database.database import Base, get_db
from app.main import app
from app.models.usuario import Usuario

API_KEY = "dev-secret-key-change-me"
API_PREFIX = "/api/v1"
ITEMS_BASE = f"{API_PREFIX}/items"


def rand_sku(prefix: str = "CAJA") -> str:
    return f"{prefix}-{''.join(random.choices(string.digits, k=6))}"


@pytest.fixture(scope="function")
def setup_db(tmp_path: Path):
    """
    BD limpia por test (sqlite archivo temporal) + override get_db
    """
    test_db_path = tmp_path / "test.db"
    test_db_url = f"sqlite:///{test_db_path}"

    engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(setup_db):
    with TestClient(app) as c:
        yield c


def _ensure_user(
    TestingSessionLocal,
    *,
    email: str,
    password: str,
    rol: str,
) -> str:
    """
    Crea o actualiza un usuario de prueba y devuelve un access token.
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
            db.commit()
            db.refresh(user)

        token = create_access_token(user.email)
        return token
    finally:
        db.close()


@pytest.fixture()
def auth_headers(setup_db) -> dict[str, str]:
    """
    Headers de autenticación para la mayoría de tests de escritura.
    Usa rol editor porque editor/admin pueden crear/actualizar.
    """
    token = _ensure_user(
        setup_db,
        email="editor@test.com",
        password="Test123456",
        rol="editor",
    )
    return {
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture()
def admin_auth_headers(setup_db) -> dict[str, str]:
    """
    Headers de autenticación con rol admin.
    Útil para tests que requieren eliminar.
    """
    token = _ensure_user(
        setup_db,
        email="admin@test.com",
        password="Test123456",
        rol="admin",
    )
    return {
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {token}",
    }


@pytest.fixture()
def lector_auth_headers(setup_db) -> dict[str, str]:
    """
    Headers con rol lector para tests RBAC.
    """
    token = _ensure_user(
        setup_db,
        email="lector@test.com",
        password="Test123456",
        rol="lector",
    )
    return {
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {token}",
    }


def unwrap(resp_json: dict) -> dict:
    """
    Valida wrapper ApiResponse y regresa el dict completo.
    """
    assert isinstance(resp_json, dict)
    assert "success" in resp_json
    assert "message" in resp_json
    assert "data" in resp_json
    assert "metadata" in resp_json
    return resp_json


def request_id_from(resp) -> str:
    rid = resp.headers.get("x-request-id")
    assert rid is not None and len(rid) > 0
    return rid


def create_item(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    name: str,
    price: float,
    stock: int,
    sku_prefix: str = "T",
    codigo_sku: str = "AB-1234",
) -> dict[str, Any]:
    payload = {
        "name": name,
        "description": "para test",
        "price": price,
        "sku": rand_sku(sku_prefix),
        "codigo_sku": codigo_sku,
        "stock": stock,
    }
    r = client.post(f"{ITEMS_BASE}/", headers=auth_headers, json=payload)
    assert r.status_code in (200, 201), r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True
    assert isinstance(body["data"], dict)
    return body["data"]


def get_items_wrapped(client: TestClient, auth_headers: dict[str, str], query: str = "") -> dict:
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
    url = f"{ITEMS_BASE}/eliminados" + (f"?{query}" if query else "")
    r = client.get(url, headers=auth_headers)
    assert r.status_code == 200, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True
    assert isinstance(body["data"], dict)
    assert "items" in body["data"]
    return body