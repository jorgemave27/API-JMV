from __future__ import annotations


def test_request_logging_middleware_no_rompe_requests(client, auth_headers):
    r = client.get("/items/?page=1&page_size=10", headers=auth_headers)
    assert r.status_code == 200, r.text


def test_create_item_con_logging_sigue_funcionando(client, auth_headers):
    payload = {
        "name": "caja logs",
        "description": "test",
        "price": 10.0,
        "sku": "LOGS-001",
        "codigo_sku": "AB-1234",
        "stock": 1,
    }
    r = client.post("/items/", headers=auth_headers, json=payload)
    assert r.status_code in (200, 201), r.text