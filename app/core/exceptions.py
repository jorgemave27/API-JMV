from __future__ import annotations


class ItemNoEncontradoError(Exception):
    def __init__(self, item_id: int):
        self.item_id = item_id
        super().__init__(f"Item no encontrado: {item_id}")


class StockInsuficienteError(Exception):
    def __init__(self, item_id: int, stock_actual: int):
        self.item_id = item_id
        self.stock_actual = stock_actual
        super().__init__(
            f"No se puede marcar disponible=True para el item {item_id} "
            f"porque su stock actual es {stock_actual}"
        )