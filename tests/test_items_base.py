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


def _get_request_id_header(resp) -> str:
    rid = resp.headers.get("x-request-id")
    assert rid is not None and len(rid) > 0
    return rid


def _create_item(client: TestClient, *, name: str, price: float, stock: int, sku_prefix: str = "T") -> dict:
    payload = {
        "name": name,
        "description": "para test",
        "price": price,
        "sku": _rand_sku(sku_prefix),
        "codigo_sku": "AB-1234",
        "stock": stock,
    }
    r = client.post("/items/", headers=_auth_headers(), json=payload)
    assert r.status_code in (200, 201), r.text
    _get_request_id_header(r)

    body = _unwrap(r.json())
    assert body["success"] is True
    assert isinstance(body["data"], dict)
    return body["data"]


def _get_items_wrapped(client: TestClient, query: str = "") -> dict:
    url = "/items/" + (f"?{query}" if query else "")
    r = client.get(url, headers=_auth_headers())
    assert r.status_code == 200, r.text
    _get_request_id_header(r)

    body = _unwrap(r.json())
    assert body["success"] is True
    assert isinstance(body["data"], dict)
    assert "items" in body["data"]
    return body


def _get_deleted_wrapped(client: TestClient, query: str = "") -> dict:
    url = "/items/eliminados" + (f"?{query}" if query else "")
    r = client.get(url, headers=_auth_headers())
    assert r.status_code == 200, r.text
    _get_request_id_header(r)

    body = _unwrap(r.json())
    assert body["success"] is True
    assert isinstance(body["data"], dict)
    assert "items" in body["data"]
    return body


# ------------------------
# BASE: health + auth + CRUD + soft delete
# ------------------------

def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_create_item_requires_api_key(client):
    payload = {
        "name": "caja mediana",
        "description": "Para empaque",
        "price": 25.5,
        "sku": "CAJA-001",
        "codigo_sku": "AB-1234",
        "stock": 10,
    }
    r = client.post("/items/", json=payload)
    assert r.status_code == 401


def test_create_item_ok(client):
    payload = {
        "name": "caja industrial",
        "description": "para exportación",
        "price": 50.5,
        "sku": _rand_sku("CAJA"),
        "codigo_sku": "ZX-9999",
        "stock": 100,
    }
    r = client.post("/items/", headers=_auth_headers(), json=payload)
    assert r.status_code in (200, 201), r.text
    _get_request_id_header(r)

    body = _unwrap(r.json())
    assert body["success"] is True
    data = body["data"]
    assert data["id"] >= 1
    assert data["name"] == "Caja Industrial"
    assert data["stock"] == 100


def test_list_items_ok_paginado(client):
    _create_item(client, name="caja chica", price=10.0, stock=1, sku_prefix="LST")

    body = _get_items_wrapped(client, "page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["stock"] == 1


def test_soft_delete_oculta_en_listado_y_aparece_en_eliminados(client):
    created = _create_item(client, name="caja soft", price=10.0, stock=1, sku_prefix="SOFT")
    item_id = created["id"]

    r = client.delete(f"/items/{item_id}", headers=_auth_headers())
    assert r.status_code == 200, r.text
    _get_request_id_header(r)

    body = _unwrap(r.json())
    assert body["success"] is True

    activos = _get_items_wrapped(client, "page=1&page_size=10")
    assert activos["data"]["total"] == 0
    assert len(activos["data"]["items"]) == 0

    eliminados = _get_deleted_wrapped(client, "page=1&page_size=10")
    assert eliminados["data"]["total"] == 1
    assert len(eliminados["data"]["items"]) == 1
    assert eliminados["data"]["items"][0]["eliminado"] is True
    assert eliminados["data"]["items"][0]["eliminado_en"] is not None


def test_restaurar_falla_si_item_no_esta_eliminado(client):
    created = _create_item(client, name="caja activa", price=10.0, stock=1, sku_prefix="ACT")
    item_id = created["id"]

    r = client.post(f"/items/{item_id}/restaurar", headers=_auth_headers())
    assert r.status_code == 400, r.text
    _get_request_id_header(r)

    body = _unwrap(r.json())
    assert body["success"] is False
    assert "no está eliminado" in body["message"].lower()