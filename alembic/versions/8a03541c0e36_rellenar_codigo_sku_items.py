"""rellenar_codigo_sku_items

Revision ID: 8a03541c0e36
Revises: 5bb819cdfc5e
Create Date: 2026-03-06

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a03541c0e36"
down_revision: Union[str, Sequence[str], None] = "5bb819cdfc5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rellena codigo_sku para items que no lo tengan.

    Formato:
    - primeras 2 letras del name, en mayúsculas
    - guion
    - id con 4 dígitos

    Ejemplo:
    "Caja Premium", id=7 -> CA-0007
    """
    connection = op.get_bind()

    rows = connection.exec_driver_sql(
        """
        SELECT id, name, codigo_sku
        FROM items
        WHERE codigo_sku IS NULL OR TRIM(codigo_sku) = ''
        """
    ).fetchall()

    for row in rows:
        item_id = row[0]
        name = (row[1] or "").strip()

        # Tomar solo letras del nombre
        letters_only = "".join(ch for ch in name if ch.isalpha()).upper()

        # Prefijo de 2 letras; si no alcanza, usar IT
        if len(letters_only) >= 2:
            prefix = letters_only[:2]
        else:
            prefix = "IT"

        generated_codigo_sku = f"{prefix}-{item_id:04d}"

        connection.exec_driver_sql(
            "UPDATE items SET codigo_sku = ? WHERE id = ?",
            (generated_codigo_sku, item_id),
        )


def downgrade() -> None:
    """
    Revierte la migración limpiando codigo_sku en registros que sigan
    el patrón generado XX-0000.

    Nota:
    En un sistema real esto podría requerir una marca adicional para distinguir
    valores generados automáticamente de valores cargados manualmente.
    """
    connection = op.get_bind()

    rows = connection.exec_driver_sql("SELECT id, codigo_sku FROM items WHERE codigo_sku IS NOT NULL").fetchall()

    for row in rows:
        item_id = row[0]
        codigo_sku = (row[1] or "").strip()

        if len(codigo_sku) == 7 and codigo_sku[2] == "-" and codigo_sku[:2].isalpha() and codigo_sku[3:].isdigit():
            connection.exec_driver_sql(
                "UPDATE items SET codigo_sku = NULL WHERE id = ?",
                (item_id,),
            )
