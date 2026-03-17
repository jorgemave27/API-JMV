# app/models/__init__.py

"""
Registro central de modelos ORM.

IMPORTANTE:
SQLAlchemy necesita que todos los modelos estén importados
para poder resolver relaciones por string (ej: "Categoria").

Este archivo garantiza que todos los modelos se carguen
cuando se importe `app.models`.
"""

from app.models.item import Item
from app.models.categoria import Categoria
from app.models.auditoria_item import AuditoriaItem

# Si agregas más modelos en el futuro, agrégalos aquí