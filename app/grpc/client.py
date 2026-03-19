from __future__ import annotations

import sys
from pathlib import Path

import grpc

# -----------------------------------------------------
# Agregar root del proyecto al PYTHONPATH
# -----------------------------------------------------
sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.grpc import items_pb2, items_pb2_grpc


def get_item_via_grpc(item_id: int, host: str = "localhost:50051") -> dict:
    """
    Consulta un item vía gRPC.
    """
    with grpc.insecure_channel(host) as channel:
        stub = items_pb2_grpc.ItemServiceStub(channel)
        response = stub.GetItem(items_pb2.ItemRequest(item_id=item_id))

        return {
            "id": response.id,
            "name": response.name,
            "description": response.description,
            "price": response.price,
            "sku": response.sku,
            "codigo_sku": response.codigo_sku,
            "stock": response.stock,
            "eliminado": response.eliminado,
            "eliminado_en": response.eliminado_en,
            "categoria_id": response.categoria_id,
        }


def list_items_via_grpc(
    limit: int = 10,
    offset: int = 0,
    host: str = "localhost:50051",
) -> list[dict]:
    """
    Lista items vía gRPC usando streaming.
    """
    results: list[dict] = []

    with grpc.insecure_channel(host) as channel:
        stub = items_pb2_grpc.ItemServiceStub(channel)
        responses = stub.ListItems(items_pb2.ListRequest(limit=limit, offset=offset))

        for response in responses:
            results.append(
                {
                    "id": response.id,
                    "name": response.name,
                    "description": response.description,
                    "price": response.price,
                    "sku": response.sku,
                    "codigo_sku": response.codigo_sku,
                    "stock": response.stock,
                    "eliminado": response.eliminado,
                    "eliminado_en": response.eliminado_en,
                    "categoria_id": response.categoria_id,
                }
            )

    return results


if __name__ == "__main__":
    print(get_item_via_grpc(5))
    print(list_items_via_grpc(limit=5, offset=0))
