from __future__ import annotations

from pathlib import Path

import pytest
import requests
from pact import Pact, match

PACT_DIR = Path("tests/pacts")
PACT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.mark.contract
def test_contract_listar_items():
    pact = Pact("frontend-web", "api-jmv").with_specification("V4")

    (
        pact.upon_receiving("una solicitud para listar items")
        .given("existen items activos")
        .with_request(
            "GET",
            "/api/v1/items/",
        )
        .will_respond_with(200)
        .with_body(
            {
                "success": True,
                "message": match.str("Items obtenidos exitosamente"),
                "data": {
                    "page": match.int(1),
                    "page_size": match.int(10),
                    "total": match.int(1),
                    "items": match.each_like(
                        {
                            "id": match.int(1),
                            "name": match.str("Caja Premium"),
                            "description": match.str("Caja para ecommerce"),
                            "price": match.number(149.9),
                            "sku": match.str("CAJA-001"),
                            "codigo_sku": match.str("AB-1001"),
                            "stock": match.int(50),
                            "eliminado": match.bool(False),
                            "eliminado_en": match.none(),
                            "categoria_id": match.none(),
                        },
                        min=1,
                    ),
                },
                "metadata": match.like({}),
            },
            content_type="application/json",
        )
    )

    with pact.serve() as server:
        response = requests.get(
            f"{server.url}/api/v1/items/",
            timeout=5,
        )

        assert response.status_code == 200

        body = response.json()
        assert body["success"] is True
        assert "data" in body
        assert "items" in body["data"]

    pact.write_file(PACT_DIR)
