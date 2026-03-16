from __future__ import annotations


class ItemNoEncontradoError(Exception):
    """
    Excepción cuando un item no existe.
    Incluye data para que el exception handler pueda serializarla.
    """

    def __init__(self, item_id: int):
        self.item_id = item_id

        # mensaje esperado por tests
        self.message = f"Item no encontrado: {item_id}"

        # data requerida por tests
        self.data = {"item_id": item_id}

        super().__init__(self.message)


class StockInsuficienteError(Exception):
    """
    Excepción cuando se intenta marcar disponible=True
    pero el item tiene stock 0.
    """

    def __init__(self, item_id: int, stock_actual: int):
        self.item_id = item_id
        self.stock_actual = stock_actual

        # mensaje exacto usado por los tests
        self.message = (
            f"No se puede marcar disponible=True para el item {item_id} "
            f"porque su stock actual es {stock_actual}"
        )

        # data que usan los tests
        self.data = {
            "item_id": item_id,
            "stock_actual": stock_actual,
        }

        super().__init__(self.message)