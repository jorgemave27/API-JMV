from __future__ import annotations

"""
Métricas personalizadas de negocio para Prometheus.

Aquí definimos:
- Contador de items creados por categoría
- Histograma de precios de items vendidos
- Gauge del total de items activos
- Contador general de operaciones CRUD
- Histograma de latencia de queries a base de datos
- Gauge de conexiones WebSocket activas

Estas métricas se actualizarán desde la lógica de negocio
(servicios o endpoints) cuando ocurra cada operación.
"""

from prometheus_client import Counter, Gauge, Histogram

# =====================================================
# MÉTRICAS EXISTENTES DE NEGOCIO
# =====================================================

# Contador: cuántos items se crean por categoría
ITEMS_CREATED_BY_CATEGORY = Counter(
    "items_created_by_category_total",
    "Total de items creados por categoria",
    ["category"],
)

# Histograma: distribución de precios de items vendidos
ITEM_SOLD_PRICE_HISTOGRAM = Histogram(
    "item_sold_price_mxn",
    "Distribucion de precios de items vendidos en MXN",
    buckets=(0, 50, 100, 250, 500, 1000, 5000, 10000, float("inf")),
)

# Gauge: cuántos items activos existen actualmente
ACTIVE_ITEMS_GAUGE = Gauge(
    "active_items_total",
    "Total de items activos en el sistema",
)

# =====================================================
# MÉTRICAS NUEVAS PARA TASK 68
# =====================================================

# Contador general de operaciones CRUD por entidad / operación / resultado
CRUD_OPERATIONS_TOTAL = Counter(
    "crud_operations_total",
    "Total de operaciones CRUD ejecutadas",
    ["entity", "operation", "status"],
)

# Histograma de latencia para queries a base de datos
DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Duracion de queries a base de datos en segundos",
    ["operation", "table"],
    buckets=(
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
    ),
)

# Gauge de conexiones websocket activas
ACTIVE_WEBSOCKET_CONNECTIONS = Gauge(
    "active_websocket_connections",
    "Total de conexiones websocket activas",
)

# Gauge de usuarios activos
ACTIVE_USERS_GAUGE = Gauge(
    "active_users_total",
    "Total de usuarios activos en el sistema",
)


# =====================================================
# HELPERS
# =====================================================

def increment_crud_operation(
    entity: str,
    operation: str,
    status: str = "success",
) -> None:
    """
    Incrementa el contador general de operaciones CRUD.

    Args:
        entity: Entidad afectada, por ejemplo 'item' o 'usuario'.
        operation: Operación ejecutada, por ejemplo 'create', 'read', 'update', 'delete'.
        status: Resultado de la operación, por ejemplo 'success' o 'error'.
    """
    CRUD_OPERATIONS_TOTAL.labels(
        entity=entity,
        operation=operation,
        status=status,
    ).inc()


def increment_items_created_by_category(category: str) -> None:
    """
    Incrementa el contador de items creados para una categoría dada.
    """
    ITEMS_CREATED_BY_CATEGORY.labels(category=category).inc()


def observe_item_sold_price(price: float) -> None:
    """
    Registra un precio vendido dentro del histograma de precios.
    """
    ITEM_SOLD_PRICE_HISTOGRAM.observe(float(price))


def set_active_items(total: int) -> None:
    """
    Actualiza el gauge del total de items activos.
    """
    ACTIVE_ITEMS_GAUGE.set(float(total))


def set_active_users(total: int) -> None:
    """
    Actualiza el gauge del total de usuarios activos.
    """
    ACTIVE_USERS_GAUGE.set(float(total))


def websocket_connected() -> None:
    """
    Incrementa el número de conexiones websocket activas.
    """
    ACTIVE_WEBSOCKET_CONNECTIONS.inc()


def websocket_disconnected() -> None:
    """
    Decrementa el número de conexiones websocket activas.
    """
    ACTIVE_WEBSOCKET_CONNECTIONS.dec()