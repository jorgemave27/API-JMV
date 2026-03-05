from __future__ import annotations

import sys
from pathlib import Path

# -- root del proyecto al path
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
    """
    Crea una BD limpia para cada test:
    - usa test.db (sqlite archivo)
    - crea tablas desde Base.metadata (incluye created_at)
    - sobreescribe get_db() para que la API use esta BD
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

    yield

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(setup_db):
    with TestClient(app) as c:
        yield c


# ------------------------
# Helpers
# ------------------------

def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


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
    return r.json()


def _get_items(client: TestClient, query: str = "") -> dict:
    """
    GET /items/ ahora regresa paginado:
    { page, page_size, total, items: [...] }
    """
    url = "/items/" + (f"?{query}" if query else "")
    r = client.get(url, headers=_auth_headers())
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, dict)
    assert "items" in data
    return data


# ------------------------
# Tests base (health + auth + CRUD)
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

    data = r.json()
    assert data["id"] >= 1
    # Title Case del reto #06 (si tu API lo sigue aplicando)
    assert data["name"] == "Caja Industrial"
    assert data["stock"] == 100


def test_list_items_ok_paginado(client):
    _create_item(client, name="caja chica", price=10.0, stock=1, sku_prefix="LST")
    data = _get_items(client, "page=1&page_size=10")
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["stock"] == 1


# ------------------------
# Paginación (tarea previa) - ajustada a respuesta nueva
# ------------------------

def test_paginacion_page2_devuelve_5(client):
    for i in range(15):
        _create_item(client, name=f"caja pag {i}", price=10.5, stock=0, sku_prefix="PAG")

    data = _get_items(client, "page=2&page_size=10")
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert data["total"] == 15
    assert len(data["items"]) == 5


def test_codigo_sku_invalido_da_422(client):
    payload = {
        "name": "caja prueba sku",
        "description": "para test",
        "price": 10.0,
        "sku": _rand_sku("SKU"),
        "codigo_sku": "A1-1234",  # inválido
        "stock": 0,
    }
    r = client.post("/items/", headers=_auth_headers(), json=payload)
    assert r.status_code == 422, r.text


# ------------------------
# Soft delete - ajustado a respuesta nueva
# ------------------------

def test_soft_delete_oculta_en_listado_y_aparece_en_eliminados(client):
    created = _create_item(client, name="caja soft", price=10.0, stock=1, sku_prefix="SOFT")
    item_id = created["id"]

    r = client.delete(f"/items/{item_id}", headers=_auth_headers())
    assert r.status_code == 200, r.text

    data_activos = _get_items(client, "page=1&page_size=10")
    assert data_activos["total"] == 0
    assert len(data_activos["items"]) == 0

    r = client.get("/items/eliminados?page=1&page_size=10", headers=_auth_headers())
    assert r.status_code == 200, r.text
    data_elim = r.json()
    assert isinstance(data_elim, dict)
    assert data_elim["total"] == 1
    assert len(data_elim["items"]) == 1
    assert data_elim["items"][0]["eliminado"] is True
    assert data_elim["items"][0]["eliminado_en"] is not None


def test_restaurar_falla_si_item_no_esta_eliminado(client):
    created = _create_item(client, name="caja activa", price=10.0, stock=1, sku_prefix="ACT")
    item_id = created["id"]

    r = client.post(f"/items/{item_id}/restaurar", headers=_auth_headers())
    assert r.status_code == 400, r.text


# ------------------------
# filtros + orden + creado_desde
# ------------------------

def test_filtro_nombre_y_orden_precio_desc(client):
    _create_item(client, name="Caja Premium", price=120.5, stock=10, sku_prefix="T10")
    _create_item(client, name="Caja Economica", price=50.0, stock=0, sku_prefix="T10")
    _create_item(client, name="Bolsa Plastica", price=15.0, stock=5, sku_prefix="T10")

    data = _get_items(client, "nombre=caja&ordenar_por=precio_desc&page=1&page_size=10")
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["price"] >= data["items"][1]["price"]
    names = [x["name"].lower() for x in data["items"]]
    assert any("caja" in n for n in names)


def test_filtro_disponible_true(client):
    _create_item(client, name="Caja con stock", price=10.0, stock=5, sku_prefix="DSTK")
    _create_item(client, name="Caja sin stock", price=11.0, stock=0, sku_prefix="DSTK")

    data = _get_items(client, "nombre=caja&disponible=true&page=1&page_size=10")
    assert data["total"] == 1
    assert data["items"][0]["stock"] > 0


def test_filtro_precio_rango(client):
    _create_item(client, name="Caja 49", price=49.0, stock=1, sku_prefix="RNG")
    _create_item(client, name="Caja 50", price=50.0, stock=1, sku_prefix="RNG")
    _create_item(client, name="Caja 70", price=70.0, stock=1, sku_prefix="RNG")

    data = _get_items(client, "precio_min=40&precio_max=60&ordenar_por=precio_asc&page=1&page_size=10")
    assert data["total"] == 2
    prices = [x["price"] for x in data["items"]]
    assert all(40 <= p <= 60 for p in prices)
    assert prices == sorted(prices)


def test_filtro_creado_desde_fecha_futura_da_0(client):
    _create_item(client, name="Caja hoy", price=10.0, stock=1, sku_prefix="DATE")
    data = _get_items(client, "creado_desde=2099-01-01&page=1&page_size=10")
    assert data["total"] == 0
    assert len(data["items"]) == 0