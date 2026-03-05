from __future__ import annotations
import sys
from pathlib import Path

#--root del proyecto al path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import os
from pathlib import Path
import random
import string

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.database import Base, get_db

# API Key usada en tu proyecto (la que pusiste en Swagger)
API_KEY = "dev-secret-key-change-me"


def _rand_sku(prefix: str = "CAJA") -> str:
    return f"{prefix}-{''.join(random.choices(string.digits, k=4))}"


@pytest.fixture(scope="function")
def setup_db(tmp_path: Path):
    """
    Crea una BD limpia para cada test:
    - usa test.db (archivo)
    - crea tablas desde Base.metadata
    - sobreescribe get_db() para que la API use esta BD
    """
    test_db_path = tmp_path / "test.db"
    test_db_url = f"sqlite:///{test_db_path}"

    engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # BD limpia
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield  # aquí corre el test

    # teardown
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(setup_db):
    """
    Cliente HTTP para llamar a la API dentro de pytest
    """
    with TestClient(app) as c:
        yield c


# ------------------------
# Tests base (CRUD + auth)
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
    r = client.post("/items/", json=payload)  # sin X-API-Key
    assert r.status_code == 401


def test_create_item_ok(client):
    payload = {
        "name": "caja industrial",
        "description": "para exportación",
        "price": 50.5,
        "sku": "CAJA-900",
        "codigo_sku": "ZX-9999",
        "stock": 100,
    }
    r = client.post("/items/", headers={"X-API-Key": API_KEY}, json=payload)

    # Tu API a veces usa 200 o 201 según el manual; aceptamos ambos
    assert r.status_code in (200, 201), r.text

    data = r.json()
    assert data["id"] >= 1
    # Title Case del reto #06
    assert data["name"] == "Caja Industrial"
    assert data["sku"] == "CAJA-900"
    assert data["codigo_sku"] == "ZX-9999"
    # Stock del reto #07
    assert data["stock"] == 100


def test_list_items_ok(client):
    # crea 1 item
    payload = {
        "name": "caja chica",
        "description": "para test",
        "price": 10.0,
        "sku": "CAJA-002",
        "codigo_sku": "AB-1234",
        "stock": 1,
    }
    r1 = client.post("/items/", headers={"X-API-Key": API_KEY}, json=payload)
    assert r1.status_code in (200, 201), r1.text

    r = client.get("/items/?page=1&page_size=10", headers={"X-API-Key": API_KEY})
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["stock"] == 1


# ------------------------
# 3 pruebas nuevas
# ------------------------

def test_paginacion_page2_devuelve_5(client):
    # Crea 15 items
    for i in range(15):
        payload = {
            "name": f"caja pag {i}",
            "description": "para test",
            "price": 10.5,
            "sku": _rand_sku("PAG"),
            "codigo_sku": f"AB-{1000+i}",
            "stock": 0,
        }
        r = client.post("/items/", headers={"X-API-Key": API_KEY}, json=payload)
        assert r.status_code in (200, 201), r.text

    # Página 2 con page_size 10 => debe traer 5
    r = client.get("/items/?page=2&page_size=10", headers={"X-API-Key": API_KEY})
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 5


def test_busqueda_por_nombre(client):
    # Crea items con nombres que compartan substring
    items = [
        {"name": "Caja Industrial", "sku": _rand_sku("BUS"), "codigo_sku": "ZX-9999"},
        {"name": "Caja Chica", "sku": _rand_sku("BUS"), "codigo_sku": "ZX-9998"},
        {"name": "Bolsa Industrial", "sku": _rand_sku("BUS"), "codigo_sku": "ZX-9997"},
    ]
    for it in items:
        payload = {
            "name": it["name"],
            "description": "para test",
            "price": 20.0,
            "sku": it["sku"],
            "codigo_sku": it["codigo_sku"],
            "stock": 1,
        }
        r = client.post("/items/", headers={"X-API-Key": API_KEY}, json=payload)
        assert r.status_code in (200, 201), r.text

    # Buscar "industrial" debería traer 2 (Caja Industrial + Bolsa Industrial)
    r = client.get("/items/buscar?nombre=industrial", headers={"X-API-Key": API_KEY})
    assert r.status_code == 200, r.text
    data = r.json()
    names = [x["name"].lower() for x in data]
    assert any("caja industrial" in n for n in names)
    assert any("bolsa industrial" in n for n in names)
    assert len(data) == 2


def test_codigo_sku_invalido_da_422(client):
    #--codigo_sku debe ser AB-1234
    payload = {
        "name": "caja prueba sku",
        "description": "para test",
        "price": 10.0,
        "sku": _rand_sku("SKU"),
        "codigo_sku": "A1-1234",  #-- inválido
        "stock": 0,
    }
    r = client.post("/items/", headers={"X-API-Key": API_KEY}, json=payload)
    assert r.status_code == 422, r.text



def test_soft_delete_oculta_en_listado_y_aparece_en_eliminados(client):
#--TEST PARA SOFT DELETE (reto #08)
    payload = {
        "name": "caja soft",
        "description": "test",
        "price": 10.0,
        "sku": "SOFT-100",
        "codigo_sku": "AB-1234",
        "stock": 1,
    }
    r = client.post("/items/", headers={"X-API-Key": API_KEY}, json=payload)
    assert r.status_code in (200, 201), r.text
    item_id = r.json()["id"]

    r = client.delete(f"/items/{item_id}", headers={"X-API-Key": API_KEY})
    assert r.status_code == 200, r.text

    r = client.get("/items/?page=1&page_size=10", headers={"X-API-Key": API_KEY})
    assert r.status_code == 200
    assert len(r.json()) == 0

    r = client.get("/items/eliminados?page=1&page_size=10", headers={"X-API-Key": API_KEY})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["eliminado"] is True
    assert data[0]["eliminado_en"] is not None


def test_restaurar_falla_si_item_no_esta_eliminado(client):
    payload = {
        "name": "caja activa",
        "description": "test",
        "price": 10.0,
        "sku": "SOFT-101",
        "codigo_sku": "AB-1234",
        "stock": 1,
    }
    r = client.post("/items/", headers={"X-API-Key": API_KEY}, json=payload)
    assert r.status_code in (200, 201), r.text
    item_id = r.json()["id"]

    r = client.post(f"/items/{item_id}/restaurar", headers={"X-API-Key": API_KEY})
    assert r.status_code == 400, r.text