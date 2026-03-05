from __future__ import annotations

from tests.conftest import create_item, get_items_wrapped


def test_paginacion_page2_devuelve_5(client, auth_headers):
    for i in range(15):
        create_item(client, auth_headers, name=f"caja pag {i}", price=10.5, stock=0, sku_prefix="PAG")

    body = get_items_wrapped(client, auth_headers, "page=2&page_size=10")
    data = body["data"]
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert data["total"] == 15
    assert len(data["items"]) == 5


def test_filtro_nombre_y_orden_precio_desc(client, auth_headers):
    create_item(client, auth_headers, name="Caja Premium", price=120.5, stock=10, sku_prefix="T10")
    create_item(client, auth_headers, name="Caja Economica", price=50.0, stock=0, sku_prefix="T10")
    create_item(client, auth_headers, name="Bolsa Plastica", price=15.0, stock=5, sku_prefix="T10")

    body = get_items_wrapped(client, auth_headers, "nombre=caja&ordenar_por=precio_desc&page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["price"] >= data["items"][1]["price"]


def test_filtro_disponible_true(client, auth_headers):
    create_item(client, auth_headers, name="Caja con stock", price=10.0, stock=5, sku_prefix="DSTK")
    create_item(client, auth_headers, name="Caja sin stock", price=11.0, stock=0, sku_prefix="DSTK")

    body = get_items_wrapped(client, auth_headers, "nombre=caja&disponible=true&page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 1
    assert data["items"][0]["stock"] > 0


def test_filtro_precio_rango(client, auth_headers):
    create_item(client, auth_headers, name="Caja 49", price=49.0, stock=1, sku_prefix="RNG")
    create_item(client, auth_headers, name="Caja 50", price=50.0, stock=1, sku_prefix="RNG")
    create_item(client, auth_headers, name="Caja 70", price=70.0, stock=1, sku_prefix="RNG")

    body = get_items_wrapped(client, auth_headers, "precio_min=40&precio_max=60&ordenar_por=precio_asc&page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 2
    prices = [x["price"] for x in data["items"]]
    assert all(40 <= p <= 60 for p in prices)
    assert prices == sorted(prices)


def test_filtro_creado_desde_fecha_futura_da_0(client, auth_headers):
    create_item(client, auth_headers, name="Caja hoy", price=10.0, stock=1, sku_prefix="DATE")

    body = get_items_wrapped(client, auth_headers, "creado_desde=2099-01-01&page=1&page_size=10")
    data = body["data"]
    assert data["total"] == 0
    assert len(data["items"]) == 0