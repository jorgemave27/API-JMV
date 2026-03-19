"""normalizar_nombres_items

Revision ID: 5bb819cdfc5e
Revises: 6021b7c28b7c
Create Date: 2026-03-06 13:45:10.178871

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5bb819cdfc5e"
down_revision: Union[str, Sequence[str], None] = "6021b7c28b7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Normaliza los nombres de items a Title Case.

    Nota:
    - En este proyecto la columna real es 'name' (no 'nombre').
    - Se usa Python sobre los registros existentes porque SQLite no ofrece
      una función nativa simple para convertir texto completo a Title Case.
    """
    connection = op.get_bind()

    rows = connection.exec_driver_sql("SELECT id, name FROM items WHERE name IS NOT NULL").fetchall()

    for row in rows:
        item_id = row[0]
        current_name = row[1]

        normalized_name = current_name.strip().title()

        connection.exec_driver_sql(
            "UPDATE items SET name = ? WHERE id = ?",
            (normalized_name, item_id),
        )


def downgrade() -> None:
    """
    No es reversible.

    No se puede reconstruir con certeza el formato original de cada nombre
    antes de haber sido normalizado.
    """
    raise NotImplementedError("La migración normalizar_nombres_items no es reversible.")
