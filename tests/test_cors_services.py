from __future__ import annotations


def test_cors_preflight_allows_configured_origin(client):
    response = client.options(
        "/api/v1/items/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code in (200, 204), response.text
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_preflight_rejects_unknown_origin(client):
    response = client.options(
        "/api/v1/items/",
        headers={
            "Origin": "http://evil.local",
            "Access-Control-Request-Method": "GET",
        },
    )

    # Dependiendo de la implementación puede responder 400
    # o simplemente no incluir el header CORS.
    assert response.status_code in (200, 204, 400), response.text
    assert response.headers.get("access-control-allow-origin") != "http://evil.local"


def test_cors_get_includes_header_for_allowed_origin(client):
    response = client.get(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"