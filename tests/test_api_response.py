from __future__ import annotations

from tests.conftest import create_item, rand_sku, request_id_from, unwrap


def test_api_response_wrapper_en_list(client, auth_headers):
    r = client.get("/api/v1/items/?page=1&page_size=10", headers=auth_headers)
    assert r.status_code == 200, r.text

    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True
    assert isinstance(body["message"], str)
    assert isinstance(body["data"], dict)
    assert "items" in body["data"]


def test_api_response_wrapper_en_create(client, auth_headers):
    payload = {
        "name": "caja apiresponse",
        "description": "test",
        "price": 10.0,
        "sku": rand_sku("AR"),
        "codigo_sku": "AB-1234",
        "stock": 1,
    }
    r = client.post("/api/v1/items/", headers=auth_headers, json=payload)
    assert r.status_code in (200, 201), r.text

    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True
    assert "creado" in body["message"].lower()
    assert isinstance(body["data"], dict)
    assert body["data"]["id"] >= 1


def test_api_response_en_error_restaurar_no_eliminado(client, auth_headers):
    created = create_item(client, auth_headers, name="caja activa", price=10.0, stock=1, sku_prefix="ERR")
    item_id = created["id"]

    r = client.post(f"/api/v1/items/{item_id}/restaurar", headers=auth_headers)
    assert r.status_code == 400, r.text

    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is False
    assert "no está eliminado" in body["message"].lower()
