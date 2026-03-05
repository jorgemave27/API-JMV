from __future__ import annotations

from tests.conftest import create_item, get_items_wrapped, rand_sku, request_id_from, unwrap


def test_bulk_create_ok(client, auth_headers):
    payload = {
        "items": [
            {
                "name": "Caja Bulk 1",
                "description": "t",
                "price": 10.0,
                "sku": rand_sku("BULK"),
                "codigo_sku": "AB-1234",
                "stock": 1,
            },
            {
                "name": "Caja Bulk 2",
                "description": "t",
                "price": 20.0,
                "sku": rand_sku("BULK"),
                "codigo_sku": "AB-1234",
                "stock": 0,
            },
        ]
    }

    r = client.post("/items/bulk", headers=auth_headers, json=payload)
    assert r.status_code in (200, 201), r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 2
    assert body["data"][0]["id"] >= 1


def test_bulk_create_rollback_si_sku_duplicado(client, auth_headers):
    dup_sku = rand_sku("DUP")

    payload = {
        "items": [
            {
                "name": "Caja Dup 1",
                "description": "t",
                "price": 10.0,
                "sku": dup_sku,
                "codigo_sku": "AB-1234",
                "stock": 1,
            },
            {
                "name": "Caja Dup 2",
                "description": "t",
                "price": 20.0,
                "sku": dup_sku,  # mismo SKU -> rompe unique en commit
                "codigo_sku": "AB-1234",
                "stock": 1,
            },
        ]
    }

    r = client.post("/items/bulk", headers=auth_headers, json=payload)
    assert r.status_code == 400, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is False

    # Verifica que no se guardó ninguno (rollback)
    items = get_items_wrapped(client, auth_headers, "page=1&page_size=100")["data"]["items"]
    skus = [x["sku"] for x in items]
    assert dup_sku not in skus


def test_bulk_delete_soft_delete(client, auth_headers):
    a = create_item(client, auth_headers, name="Caja A", price=10.0, stock=1, sku_prefix="DEL")
    b = create_item(client, auth_headers, name="Caja B", price=10.0, stock=1, sku_prefix="DEL")

    r = client.request(
        "DELETE",
        "/items/bulk",
        headers=auth_headers,
        json={"ids": [a["id"], b["id"], 999999]},
    )
    assert r.status_code == 200, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True
    assert body["data"]["deleted"] == 2
    assert body["data"]["not_found"] == 1


def test_bulk_put_disponible_actualiza_stock(client, auth_headers):
    a = create_item(client, auth_headers, name="Caja Stock 0", price=10.0, stock=0, sku_prefix="UPD")
    b = create_item(client, auth_headers, name="Caja Stock 5", price=10.0, stock=5, sku_prefix="UPD")

    # disponible=false => stock=0 (a ya está en 0, b baja a 0)
    r1 = client.put(
        "/items/bulk",
        headers=auth_headers,
        json={"ids": [a["id"], b["id"], 999999], "disponible": False},
    )
    assert r1.status_code == 200, r1.text
    request_id_from(r1)

    body1 = unwrap(r1.json())
    assert body1["success"] is True
    assert body1["data"]["not_found"] == 1
    # b sí cambió, a no cambió (ya era 0)
    assert body1["data"]["updated"] == 1

    # disponible=true => stock=1 (a sube a 1, b sube a 1)
    r2 = client.put(
        "/items/bulk",
        headers=auth_headers,
        json={"ids": [a["id"], b["id"]], "disponible": True},
    )
    assert r2.status_code == 200, r2.text
    request_id_from(r2)

    body2 = unwrap(r2.json())
    assert body2["success"] is True
    assert body2["data"]["updated"] == 2