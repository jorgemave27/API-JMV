from __future__ import annotations


def test_cors_allows_configured_origin(client):
    response = client.options(
        "/api/v1/items/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_blocks_unconfigured_origin(client):
    response = client.options(
        "/api/v1/items/",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers.get("access-control-allow-origin") is None
