from __future__ import annotations

import strawberry
from typing import List

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

# 🔥 FEDERATION
from strawberry.federation import type as federated_type, field
from strawberry.federation.schema import Schema


@federated_type(keys=["id"])
class Item:
    id: strawberry.ID

    @field
    def pedidos_asociados(self) -> List["Pedido"]:
        return [
            Pedido(id="1", total=15000, estado="COMPLETADO", items=[]),
            Pedido(id="2", total=500, estado="PENDIENTE", items=[]),
        ]


@strawberry.type
class Pedido:
    id: strawberry.ID
    total: float
    estado: str
    items: List[Item]


@strawberry.type
class Query:
    @strawberry.field
    def pedidos(self) -> List[Pedido]:
        return [
            Pedido(
                id="1",
                total=15000,
                estado="COMPLETADO",
                items=[Item(id="1")]
            ),
            Pedido(
                id="2",
                total=500,
                estado="PENDIENTE",
                items=[Item(id="2")]
            ),
        ]


schema = Schema(query=Query)

app = FastAPI()

graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")
