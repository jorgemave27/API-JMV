from __future__ import annotations


class SagaStep:
    """
    Pasos de la saga de pedido.
    """

    CREATE_PEDIDO = "CREATE_PEDIDO"
    RESERVAR_STOCK = "RESERVAR_STOCK"
    COBRAR_PAGO = "COBRAR_PAGO"
    NOTIFICAR_CLIENTE = "NOTIFICAR_CLIENTE"
    CONFIRMAR_PEDIDO = "CONFIRMAR_PEDIDO"

    COMPENSAR_STOCK = "COMPENSAR_STOCK"
    CANCELAR_PEDIDO = "CANCELAR_PEDIDO"


class SagaStatus:
    """
    Estados del log de saga.
    """

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"


class PedidoEstado:
    """
    Estados del pedido.
    """

    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    CANCELADO = "CANCELADO"


class SagaQueue:
    """
    Colas RabbitMQ para choreography.
    """

    CREATE_PEDIDO = "saga.pedido.create"
    RESERVAR_STOCK = "saga.pedido.stock.reserve"
    COBRAR_PAGO = "saga.pedido.payment.charge"
    NOTIFICAR_CLIENTE = "saga.pedido.notification.send"
    CONFIRMAR_PEDIDO = "saga.pedido.confirm"

    COMPENSAR_STOCK = "saga.pedido.stock.release"
    CANCELAR_PEDIDO = "saga.pedido.cancel"