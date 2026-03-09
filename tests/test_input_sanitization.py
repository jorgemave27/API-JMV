from __future__ import annotations

import logging


def test_create_item_sanitizes_html_in_name_and_description(client, admin_auth_headers):
    """
    Verifica que HTML simple se limpie en campos de texto.
    No usamos payload XSS agresivo aquí porque eso ahora lo bloquea
    el middleware de threat detection.
    """
    response = client.post(
        "/api/v1/items/",
        json={
            "name": "<b>caja premium</b>",
            "description": "<i>descripcion limpia</i>",
            "price": 100.0,
            "sku": "SANITIZE-001",
            "codigo_sku": "SA-1001",
            "stock": 5,
        },
        headers=admin_auth_headers,
    )

    assert response.status_code == 200

    body = response.json()
    data = body["data"]

    assert data["name"] == "Caja Premium"
    assert data["description"] == "descripcion limpia"


def test_create_item_rejects_only_spaces_in_name(client, admin_auth_headers):
    """
    Verifica que no se acepten nombres vacíos o solo con espacios.
    """
    response = client.post(
        "/api/v1/items/",
        json={
            "name": "     ",
            "description": "descripcion válida",
            "price": 100.0,
            "sku": "SANITIZE-002",
            "codigo_sku": "SB-1001",
            "stock": 5,
        },
        headers=admin_auth_headers,
    )

    assert response.status_code == 422


def test_create_item_rejects_invalid_content_type(client, admin_auth_headers):
    """
    Verifica que el endpoint rechace Content-Type distinto de application/json.
    """
    response = client.post(
        "/api/v1/items/",
        content='{"name":"Caja","description":"x","price":10,"sku":"SANITIZE-003","codigo_sku":"SC-1001","stock":1}',
        headers={
            **admin_auth_headers,
            "Content-Type": "text/plain",
        },
    )

    assert response.status_code == 415


def test_threat_detection_blocks_xss_in_query_params(client, auth_headers, caplog):
    """
    Verifica que el middleware bloquee payloads XSS sospechosos en query params.
    """
    with caplog.at_level(logging.CRITICAL):
        response = client.get(
            "/api/v1/items/buscar",
            params={"nombre": "<script>alert(1)</script>"},
            headers=auth_headers,
        )

    assert response.status_code == 400
    assert "Payload sospechoso detectado" in caplog.text


def test_threat_detection_blocks_path_traversal_in_body(client, admin_auth_headers, caplog):
    """
    Verifica que el middleware bloquee path traversal en body.
    """
    with caplog.at_level(logging.CRITICAL):
        response = client.post(
            "/api/v1/items/",
            json={
                "name": "../etc/passwd",
                "description": "payload traversal",
                "price": 100.0,
                "sku": "SANITIZE-004",
                "codigo_sku": "SD-1001",
                "stock": 5,
            },
            headers=admin_auth_headers,
        )

    assert response.status_code == 400
    assert "Payload sospechoso detectado" in caplog.text