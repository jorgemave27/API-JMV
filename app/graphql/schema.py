from __future__ import annotations

import strawberry
from typing import List, Optional

# 🔥 FEDERATION IMPORTANTE
from strawberry.federation.schema import Schema
from strawberry.federation import type as federated_type, field

# ==============================
# ENTITY FEDERADA
# ==============================
@federated_type(keys=["id"])
class Item:
    id: strawberry.ID
    name: str
    price: float
    stock: int

    # 🔥 resolver para federation
    @classmethod
    def resolve_reference(cls, id: strawberry.ID):
        # ⚠️ AQUÍ puedes conectar a DB real si quieres
        return Item(
            id=id,
            name="Item federado",
            price=100.0,
            stock=10,
        )


# ==============================
# QUERY
# ==============================
@strawberry.type
class Query:

    @strawberry.field
    def item(self, id: strawberry.ID) -> Optional[Item]:
        return Item(
            id=id,
            name="Item demo",
            price=50.0,
            stock=5,
        )

    @strawberry.field
    def items(self) -> List[Item]:
        return [
            Item(id="1", name="Laptop", price=15000, stock=3),
            Item(id="2", name="Mouse", price=500, stock=10),
        ]


# ==============================
# SCHEMA FEDERADO
# ==============================
schema = Schema(query=Query)