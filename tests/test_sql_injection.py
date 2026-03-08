from __future__ import annotations

import logging


def test_busqueda_segura_trata_payload_como_texto(client, auth_headers):
    response = client.get(
        "/api/v1/items/buscar",
        params={"nombre": "laptop' OR '1'='1"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


def test_sql_injection_warning_middleware_loguea_warning(client, auth_headers, caplog):
    with caplog.at_level(logging.WARNING):
        response = client.get(
            "/api/v1/items/buscar",
            params={"nombre": "abc' OR '1'='1"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    assert "Posible intento de inyección SQL detectado" in caplog.text