from __future__ import annotations


def test_metrics_endpoint_available(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    body = response.text
    assert len(body) > 0
