from __future__ import annotations

"""
Métricas personalizadas de negocio para Prometheus.

Aquí definimos:
- Contador de items creados por categoría
- Histograma de precios de items vendidos
- Gauge del total de items activos

Estas métricas se actualizarán desde la lógica de negocio
(servicios o endpoints) cuando ocurra cada operación.
"""

from prometheus_client import Counter, Gauge, Histogram

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