from __future__ import annotations

import uuid


def test_listar_items_rate_limit_anonimo(client):
    """
    Cliente anónimo: solo API key, sin JWT.
    Debe contar como anónimo => 50/minute.
    """
    headers = {
        "X-API-Key": "dev-secret-key-change-me",
    }

    last_response = None

    for _ in range(51):
        last_response = client.get("/api/v1/items/", headers=headers)

    assert last_response is not None
    assert last_response.status_code == 429


def test_listar_items_no_pega_rate_limit_rapido_para_autenticado(client, auth_headers):
    """
    auth_headers sí lleva JWT.
    Debe contar como autenticado => 1000/minute.
    Con 51 requests NO debería devolver 429.
    """
    last_response = None

    for _ in range(51):
        last_response = client.get("/api/v1/items/", headers=auth_headers)

    assert last_response is not None
    assert last_response.status_code == 200


def test_crear_item_no_pega_rate_limit_rapido_para_autenticado(client, admin_auth_headers):
    """
    admin_auth_headers lleva JWT válido.
    Debe contar como autenticado => 1000/minute.
    Con 11 requests NO debería devolver 429.
    """
    last_response = None

    for i in range(11):
        payload = {
            "name": f"Item Rate {i}",
            "description": "test rate limit",
            "price": 10.0,
            "sku": f"RATE-{uuid.uuid4().hex[:8]}",
            "codigo_sku": f"AB-{1000 + i}",
            "stock": 1,
        }

        last_response = client.post(
            "/api/v1/items/",
            json=payload,
            headers=admin_auth_headers,
        )

    assert last_response is not None
    assert last_response.status_code == 200
