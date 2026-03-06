from __future__ import annotations

from tests.conftest import create_item, get_deleted_wrapped, get_items_wrapped, request_id_from, unwrap, rand_sku

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
    r = client.post("/api/v1/items/", json=payload)
    assert r.status_code == 401


def test_create_item_ok(client, auth_headers):
    payload = {
        "name": "caja industrial",
        "description": "para exportación",
        "price": 50.5,
        "sku": rand_sku("CAJA"),
        "codigo_sku": "ZX-9999",
        "stock": 100,
    }
    r = client.post("/api/v1/items/", headers=auth_headers, json=payload)
    assert r.status_code in (200, 201), r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True
    data = body["data"]
    assert data["id"] >= 1
    assert data["name"] == "Caja Industrial"
    assert data["stock"] == 100


def test_list_items_ok_paginado(client, auth_headers):
    create_item(client, auth_headers, name="caja chica", price=10.0, stock=1, sku_prefix="LST")

    body = get_items_wrapped(client, auth_headers, "page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["stock"] == 1


def test_soft_delete_oculta_en_listado_y_aparece_en_eliminados(client, auth_headers):
    created = create_item(client, auth_headers, name="caja soft", price=10.0, stock=1, sku_prefix="SOFT")
    item_id = created["id"]

    r = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert r.status_code == 200, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True

    activos = get_items_wrapped(client, auth_headers, "page=1&page_size=10")
    assert activos["data"]["total"] == 0
    assert len(activos["data"]["items"]) == 0

    eliminados = get_deleted_wrapped(client, auth_headers, "page=1&page_size=10")
    assert eliminados["data"]["total"] == 1
    assert len(eliminados["data"]["items"]) == 1
    assert eliminados["data"]["items"][0]["eliminado"] is True
    assert eliminados["data"]["items"][0]["eliminado_en"] is not None


def test_restaurar_falla_si_item_no_esta_eliminado(client, auth_headers):
    created = create_item(client, auth_headers, name="caja activa", price=10.0, stock=1, sku_prefix="ACT")
    item_id = created["id"]

    r = client.post(f"/api/v1/items/{item_id}/restaurar", headers=auth_headers)
    assert r.status_code == 400, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is False
    assert "no está eliminado" in body["message"].lower()

def test_create_item_con_categoria_valida(client, auth_headers):
    # Primero creamos una categoría válida
    categoria_payload = {
        "nombre": "Empaque",
        "descripcion": "Material de empaque",
    }

    categoria_resp = client.post(
        "/categorias/",
        headers=auth_headers,
        json=categoria_payload,
    )
    assert categoria_resp.status_code in (200, 201), categoria_resp.text
    request_id_from(categoria_resp)

    categoria_body = unwrap(categoria_resp.json())
    assert categoria_body["success"] is True
    categoria_id = categoria_body["data"]["id"]

    # Luego creamos un item apuntando a esa categoría
    item_payload = {
        "name": "caja con categoria",
        "description": "test relacion",
        "price": 25.5,
        "sku": rand_sku("CAT"),
        "codigo_sku": "AB-1234",
        "stock": 10,
        "categoria_id": categoria_id,
    }

    r = client.post("/api/v1/items/", headers=auth_headers, json=item_payload)
    assert r.status_code in (200, 201), r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True

    data = body["data"]
    assert data["categoria_id"] == categoria_id
    assert data["categoria"] is not None
    assert data["categoria"]["id"] == categoria_id
    assert data["categoria"]["nombre"] == "Empaque"


def test_create_item_con_categoria_invalida_da_400(client, auth_headers):
    payload = {
        "name": "caja categoria invalida",
        "description": "test error categoria",
        "price": 25.5,
        "sku": rand_sku("ERRCAT"),
        "codigo_sku": "AB-1234",
        "stock": 10,
        "categoria_id": 999,
    }

    r = client.post("/api/v1/items/", headers=auth_headers, json=payload)
    assert r.status_code == 400, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is False
    assert "no existe" in body["message"].lower()
    assert "categoría" in body["message"].lower()