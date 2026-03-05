from __future__ import annotations

from tests.conftest import create_item, rand_sku, request_id_from, unwrap


def test_validation_error_handler_formatea_422(client, auth_headers):
    payload = {
        "name": "x",  # muy corto si tu schema exige más
        "description": "test",
        "price": 10.123,  # si tu validador rechaza >2 decimales
        "sku": rand_sku("VAL"),
        "codigo_sku": "MAL",  # inválido
        "stock": 1,
    }
    r = client.post("/items/", headers=auth_headers, json=payload)
    assert r.status_code == 422, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is False
    assert "validación" in body["message"].lower()
    assert "errors" in body["data"]


def test_item_no_encontrado_handler_devuelve_404_estandar(client, auth_headers):
    r = client.delete("/items/999999", headers=auth_headers)
    assert r.status_code == 404, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is False
    assert "no encontrado" in body["message"].lower()
    assert body["data"]["item_id"] == 999999


def test_stock_insuficiente_handler_devuelve_409(client, auth_headers):
    item = create_item(
        client,
        auth_headers,
        name="Caja sin stock",
        price=10.0,
        stock=0,
        sku_prefix="STK",
    )

    r = client.put(
        "/items/bulk",
        headers=auth_headers,
        json={"ids": [item["id"]], "disponible": True},
    )
    assert r.status_code == 409, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is False
    assert "stock actual es 0" in body["message"].lower()
    assert body["data"]["item_id"] == item["id"]
    assert body["data"]["stock_actual"] == 0