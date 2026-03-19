from __future__ import annotations

import logging


def test_busqueda_segura_bloquea_payload_sql_sospechoso(client, auth_headers):
    """
    middleware de threat detection bloquea
    payloads sospechosos antes de llegar al endpoint.
    """
    response = client.get(
        "/api/v1/items/buscar",
        params={"nombre": "laptop' OR '1'='1"},
        headers=auth_headers,
    )

    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Solicitud inválida"


def test_sql_injection_warning_middleware_loguea_warning_y_threat_detection_bloquea(
    client,
    auth_headers,
    caplog,
):
    with caplog.at_level(logging.WARNING):
        response = client.get(
            "/api/v1/items/buscar",
            params={"nombre": "abc' OR '1'='1"},
            headers=auth_headers,
        )

    assert response.status_code == 400
    assert "Posible intento de inyección SQL detectado" in caplog.text
    assert "Payload sospechoso detectado" in caplog.text
