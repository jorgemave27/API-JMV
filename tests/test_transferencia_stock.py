from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.movimiento_stock import MovimientoStock
from tests.conftest import create_item


def test_transferir_stock_rollback(client, auth_headers: dict[str, str], setup_db):
    origen = create_item(
        client,
        auth_headers,
        name="Origen rollback",
        price=100.0,
        stock=10,
        sku_prefix="RB1",
        codigo_sku="AB-9001",
    )
    destino = create_item(
        client,
        auth_headers,
        name="Destino rollback",
        price=100.0,
        stock=5,
        sku_prefix="RB2",
        codigo_sku="AB-9002",
    )

    response = client.post(
        "/api/v1/items/transferir-stock",
        headers=auth_headers,
        json={
            "item_origen_id": origen["id"],
            "item_destino_id": destino["id"],
            "cantidad": 3,
            "usuario": "test-user",
            "forzar_error": True,
        },
    )

    assert response.status_code == 500

    TestingSessionLocal = setup_db
    db: Session = TestingSessionLocal()
    try:
        origen_db = db.get(Item, origen["id"])
        destino_db = db.get(Item, destino["id"])

        assert origen_db is not None
        assert destino_db is not None

        assert origen_db.stock == 10
        assert destino_db.stock == 5

        movimientos = db.query(MovimientoStock).all()
        assert len(movimientos) == 0
    finally:
        db.close()


def test_transferir_stock_ok(client, auth_headers: dict[str, str], setup_db):
    origen = create_item(
        client,
        auth_headers,
        name="Origen ok",
        price=100.0,
        stock=20,
        sku_prefix="OK1",
        codigo_sku="AB-9101",
    )
    destino = create_item(
        client,
        auth_headers,
        name="Destino ok",
        price=100.0,
        stock=4,
        sku_prefix="OK2",
        codigo_sku="AB-9102",
    )

    response = client.post(
        "/api/v1/items/transferir-stock",
        headers=auth_headers,
        json={
            "item_origen_id": origen["id"],
            "item_destino_id": destino["id"],
            "cantidad": 6,
            "usuario": "test-user",
            "forzar_error": False,
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert body["data"]["stock_origen"] == 14
    assert body["data"]["stock_destino"] == 10
    assert body["data"]["cantidad_transferida"] == 6
    assert body["data"]["usuario"] == "test-user"

    TestingSessionLocal = setup_db
    db: Session = TestingSessionLocal()
    try:
        origen_db = db.get(Item, origen["id"])
        destino_db = db.get(Item, destino["id"])

        assert origen_db is not None
        assert destino_db is not None

        assert origen_db.stock == 14
        assert destino_db.stock == 10

        movimientos = db.query(MovimientoStock).all()
        assert len(movimientos) == 1
        assert movimientos[0].item_origen_id == origen["id"]
        assert movimientos[0].item_destino_id == destino["id"]
        assert movimientos[0].cantidad == 6
        assert movimientos[0].usuario == "test-user"
    finally:
        db.close()