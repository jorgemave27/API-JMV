from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import random
import string

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.database import Base, get_db

API_KEY = "dev-secret-key-change-me"


def _rand_sku(prefix: str = "CAJA") -> str:
    return f"{prefix}-{''.join(random.choices(string.digits, k=6))}"


@pytest.fixture(scope="function")
def setup_db(tmp_path: Path):
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
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(setup_db):
    with TestClient(app) as c:
        yield c


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


def _unwrap(resp_json: dict) -> dict:
    assert isinstance(resp_json, dict)
    assert "success" in resp_json
    assert "message" in resp_json
    assert "data" in resp_json
    assert "metadata" in resp_json
    return resp_json


def test_api_response_wrapper_en_list(client):
    r = client.get("/items/?page=1&page_size=10", headers=_auth_headers())
    assert r.status_code == 200, r.text

    # request id debe venir en header
    rid = r.headers.get("x-request-id")
    assert rid is not None and len(rid) > 0

    body = _unwrap(r.json())
    assert body["success"] is True
    assert isinstance(body["message"], str)
    assert isinstance(body["data"], dict)
    assert "items" in body["data"]


def test_api_response_wrapper_en_create(client):
    payload = {
        "name": "caja apiresponse",
        "description": "test",
        "price": 10.0,
        "sku": _rand_sku("AR"),
        "codigo_sku": "AB-1234",
        "stock": 1,
    }
    r = client.post("/items/", headers=_auth_headers(), json=payload)
    assert r.status_code in (200, 201), r.text

    rid = r.headers.get("x-request-id")
    assert rid is not None and len(rid) > 0

    body = _unwrap(r.json())
    assert body["success"] is True
    assert "creado" in body["message"].lower()
    assert isinstance(body["data"], dict)
    assert body["data"]["id"] >= 1


def test_api_response_en_error_restaurar_no_eliminado(client):
    # crea un item activo
    payload = {
        "name": "caja activa",
        "description": "test",
        "price": 10.0,
        "sku": _rand_sku("ERR"),
        "codigo_sku": "AB-1234",
        "stock": 1,
    }
    r1 = client.post("/items/", headers=_auth_headers(), json=payload)
    assert r1.status_code in (200, 201), r1.text
    item_id = _unwrap(r1.json())["data"]["id"]

    # restaurar debe dar error estandar
    r2 = client.post(f"/items/{item_id}/restaurar", headers=_auth_headers())
    assert r2.status_code == 400, r2.text

    rid = r2.headers.get("x-request-id")
    assert rid is not None and len(rid) > 0

    body = _unwrap(r2.json())
    assert body["success"] is False
    assert "no está eliminado" in body["message"].lower()