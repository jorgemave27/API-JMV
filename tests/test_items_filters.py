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
    return body["data"]


def _get_items(client: TestClient, query: str = "") -> dict:
    url = "/items/" + (f"?{query}" if query else "")
    r = client.get(url, headers=_auth_headers())
    assert r.status_code == 200, r.text
    _get_request_id_header(r)

    body = _unwrap(r.json())
    assert body["success"] is True
    assert isinstance(body["data"], dict)
    assert "items" in body["data"]
    return body


# ------------------------
# TAREA 10: filtros + orden + creado_desde + paginación
# ------------------------

def test_paginacion_page2_devuelve_5(client):
    for i in range(15):
        _create_item(client, name=f"caja pag {i}", price=10.5, stock=0, sku_prefix="PAG")

    body = _get_items(client, "page=2&page_size=10")
    data = body["data"]
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert data["total"] == 15
    assert len(data["items"]) == 5


def test_filtro_nombre_y_orden_precio_desc(client):
    _create_item(client, name="Caja Premium", price=120.5, stock=10, sku_prefix="T10")
    _create_item(client, name="Caja Economica", price=50.0, stock=0, sku_prefix="T10")
    _create_item(client, name="Bolsa Plastica", price=15.0, stock=5, sku_prefix="T10")

    body = _get_items(client, "nombre=caja&ordenar_por=precio_desc&page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["price"] >= data["items"][1]["price"]


def test_filtro_disponible_true(client):
    _create_item(client, name="Caja con stock", price=10.0, stock=5, sku_prefix="DSTK")
    _create_item(client, name="Caja sin stock", price=11.0, stock=0, sku_prefix="DSTK")

    body = _get_items(client, "nombre=caja&disponible=true&page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 1
    assert data["items"][0]["stock"] > 0


def test_filtro_precio_rango(client):
    _create_item(client, name="Caja 49", price=49.0, stock=1, sku_prefix="RNG")
    _create_item(client, name="Caja 50", price=50.0, stock=1, sku_prefix="RNG")
    _create_item(client, name="Caja 70", price=70.0, stock=1, sku_prefix="RNG")

    body = _get_items(client, "precio_min=40&precio_max=60&ordenar_por=precio_asc&page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 2
    prices = [x["price"] for x in data["items"]]
    assert all(40 <= p <= 60 for p in prices)
    assert prices == sorted(prices)


def test_filtro_creado_desde_fecha_futura_da_0(client):
    _create_item(client, name="Caja hoy", price=10.0, stock=1, sku_prefix="DATE")

    body = _get_items(client, "creado_desde=2099-01-01&page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 0
    assert len(data["items"]) == 0