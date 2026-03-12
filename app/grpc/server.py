from __future__ import annotations

import sys
from concurrent import futures
from pathlib import Path

import grpc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# -----------------------------------------------------
# Agregar root del proyecto al PYTHONPATH
# -----------------------------------------------------
sys.path.append(str(Path(__file__).resolve().parents[2]))

# -----------------------------------------------------
# Importar modelos relacionados antes de usar Item
# para que SQLAlchemy resuelva correctamente relaciones.
# -----------------------------------------------------
from app.models.categoria import Categoria
from app.models.item import Item
from app.grpc import items_pb2, items_pb2_grpc


# -----------------------------------------------------
# Engine / Session para gRPC server
# Este proceso corre desde tu Mac y PostgreSQL vive en Docker,
# por eso usamos localhost:5432
# -----------------------------------------------------
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/api_jmv"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def _to_item_response(item: Item) -> items_pb2.ItemResponse:
    """
    Convierte el modelo Item a respuesta gRPC.
    """
    return items_pb2.ItemResponse(
        id=item.id,
        name=item.name or "",
        description=item.description or "",
        price=float(item.price or 0),
        sku=item.sku or "",
        codigo_sku=item.codigo_sku or "",
        stock=int(item.stock or 0),
        eliminado=bool(item.eliminado),
        eliminado_en=item.eliminado_en.isoformat() if item.eliminado_en else "",
        categoria_id=item.categoria_id or 0,
    )


class ItemServicer(items_pb2_grpc.ItemServiceServicer):
    """
    Implementación del servicio gRPC para items.
    """

    def GetItem(self, request, context):
        """
        Obtiene un item por ID.
        """
        db = SessionLocal()
        try:
            item = (
                db.query(Item)
                .filter(Item.id == request.item_id)
                .first()
            )

            if item is None:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Item no encontrado")
                return items_pb2.ItemResponse()

            return _to_item_response(item)

        finally:
            db.close()

    def ListItems(self, request, context):
        """
        Lista items usando streaming gRPC.
        """
        db = SessionLocal()
        try:
            limit = request.limit or 10
            offset = request.offset or 0

            items = (
                db.query(Item)
                .order_by(Item.id.asc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            for item in items:
                yield _to_item_response(item)

        finally:
            db.close()


def serve():
    """
    Levanta el servidor gRPC en el puerto 50051.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    items_pb2_grpc.add_ItemServiceServicer_to_server(ItemServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()

    print("Servidor gRPC escuchando en puerto 50051")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()