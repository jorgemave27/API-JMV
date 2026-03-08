from __future__ import annotations


def test_lector_no_puede_crear_items(client, lector_auth_headers):
    payload = {
        "name": "Caja prohibida",
        "description": "lector no debe crear",
        "price": 15.0,
        "sku": "RBAC-TEST-001",
        "codigo_sku": "RB-2001",
        "stock": 3,
    }

    response = client.post(
        "/api/v1/items/",
        json=payload,
        headers=lector_auth_headers,
    )

    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert "Permisos insuficientes" in body["message"]