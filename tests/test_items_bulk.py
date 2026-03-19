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

    r = client.post("/api/v1/items/bulk", headers=auth_headers, json=payload)
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

    r = client.post("/api/v1/items/bulk", headers=auth_headers, json=payload)
    assert r.status_code == 400, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is False

    # Verifica que no se guardó ninguno (rollback)
    items = get_items_wrapped(client, auth_headers, "page=1&page_size=100")["data"]["items"]
    skus = [x["sku"] for x in items]
    assert dup_sku not in skus


def test_bulk_delete_soft_delete(client, auth_headers, admin_auth_headers):
    a = create_item(client, auth_headers, name="Caja A", price=10.0, stock=1, sku_prefix="DEL")
    b = create_item(client, auth_headers, name="Caja B", price=10.0, stock=1, sku_prefix="DEL")

    r = client.request(
        "DELETE",
        "/api/v1/items/bulk",
        headers=admin_auth_headers,
        json={"ids": [a["id"], b["id"], 999999]},
    )
    assert r.status_code == 200, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True
    assert body["data"]["deleted"] == 2
    assert body["data"]["not_found"] == 1


def test_bulk_put_disponible_false_actualiza_stock(client, auth_headers):
    """
    Este test valida el comportamiento del endpoint PUT /items/bulk
    cuando se solicita disponible=False
    """
    # Creamos item A con stock 0
    a = create_item(
        client,
        auth_headers,
        name="Caja Stock 0",
        price=10.0,
        stock=0,
        sku_prefix="UPD",
    )

    # Creamos item B con stock 5
    b = create_item(
        client,
        auth_headers,
        name="Caja Stock 5",
        price=10.0,
        stock=5,
        sku_prefix="UPD",
    )

    # Ejecutamos bulk update
    r = client.put(
        "/api/v1/items/bulk",
        headers=auth_headers,
        json={
            "ids": [a["id"], b["id"], 999999],  # incluimos un ID inexistente
            "disponible": False,
        },
    )

    # La operación debe ser exitosa
    assert r.status_code == 200, r.text

    # Verificamos que el middleware haya generado request_id
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True

    # Debe detectar el ID inexistente
    assert body["data"]["not_found"] == 1

    # Solo B cambió (5 -> 0)
    # A ya estaba en 0
    assert body["data"]["updated"] == 1


def test_bulk_put_disponible_true_con_stock_cero_da_409(client, auth_headers):
    """
    Este test valida la regla:

    Si se intenta marcar disponible=True para un item con stock=0,
    el sistema debe lanzar la excepción personalizada
    """

    # Creamos item A con stock 0
    a = create_item(
        client,
        auth_headers,
        name="Caja Stock 0",
        price=10.0,
        stock=0,
        sku_prefix="UPD",
    )

    # Creamos item B con stock 5
    b = create_item(
        client,
        auth_headers,
        name="Caja Stock 5",
        price=10.0,
        stock=5,
        sku_prefix="UPD",
    )

    # Intentamos marcar ambos como disponibles
    r = client.put(
        "/api/v1/items/bulk",
        headers=auth_headers,
        json={
            "ids": [a["id"], b["id"]],
            "disponible": True,
        },
    )

    # Debe fallar con conflicto
    assert r.status_code == 409, r.text

    # Validamos request_id del middleware
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is False

    # Validamos el mensaje de error
    assert "stock actual es 0" in body["message"].lower()

    # Validamos que indique el item problemático
    assert body["data"]["item_id"] == a["id"]
    assert body["data"]["stock_actual"] == 0
