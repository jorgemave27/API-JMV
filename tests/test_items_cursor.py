from __future__ import annotations

from tests.conftest import create_item, request_id_from, unwrap


def test_items_cursor_pagination_completa(client, auth_headers):
    # Crear 25 items
    for i in range(25):
        create_item(
            client,
            auth_headers,
            name=f"Item cursor {i + 1}",
            price=10.0 + i,
            stock=1,
            sku_prefix=f"C{i + 1}",
            codigo_sku=f"AB-{1000 + i}",
        )

    # Página 1
    r1 = client.get(
        "/api/v1/items/cursor?cursor=0&limite=10",
        headers=auth_headers,
    )
    assert r1.status_code == 200, r1.text
    request_id_from(r1)

    body1 = unwrap(r1.json())
    assert body1["success"] is True
    assert len(body1["data"]["items"]) == 10
    assert body1["data"]["has_more"] is True
    assert body1["data"]["next_cursor"] is not None

    cursor1 = body1["data"]["next_cursor"]

    # Página 2
    r2 = client.get(
        f"/api/v1/items/cursor?cursor={cursor1}&limite=10",
        headers=auth_headers,
    )
    assert r2.status_code == 200, r2.text
    request_id_from(r2)

    body2 = unwrap(r2.json())
    assert body2["success"] is True
    assert len(body2["data"]["items"]) == 10
    assert body2["data"]["has_more"] is True
    assert body2["data"]["next_cursor"] is not None

    cursor2 = body2["data"]["next_cursor"]

    # Página 3
    r3 = client.get(
        f"/api/v1/items/cursor?cursor={cursor2}&limite=10",
        headers=auth_headers,
    )
    assert r3.status_code == 200, r3.text
    request_id_from(r3)

    body3 = unwrap(r3.json())
    assert body3["success"] is True
    assert len(body3["data"]["items"]) == 5
    assert body3["data"]["has_more"] is False
    assert body3["data"]["next_cursor"] is not None

    # Verificar que no haya duplicados entre páginas
    ids_1 = [item["id"] for item in body1["data"]["items"]]
    ids_2 = [item["id"] for item in body2["data"]["items"]]
    ids_3 = [item["id"] for item in body3["data"]["items"]]

    assert len(set(ids_1 + ids_2 + ids_3)) == 25


def test_items_cursor_vacio(client, auth_headers):
    r = client.get(
        "/api/v1/items/cursor?cursor=0&limite=10",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    request_id_from(r)

    body = unwrap(r.json())
    assert body["success"] is True
    assert body["data"]["items"] == []
    assert body["data"]["next_cursor"] is None
    assert body["data"]["has_more"] is False