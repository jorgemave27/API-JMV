"""add usuario_id to auditoria_items (SAFE SQLITE - ALREADY EXISTS)"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6c5ce50a097c"
down_revision: Union[str, Sequence[str], None] = "bd5191c36a17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    🔥 FIX CRÍTICO:

    La columna `usuario_id` ya fue creada en la migración inicial:
    c6ea1aa925a5_add_auditoria_items

    Si intentamos agregarla otra vez:
    ❌ SQLite truena con "duplicate column name"

    👉 SOLUCIÓN:
    No hacer nada (no-op)
    """

    # NO HACER NADA
    pass


def downgrade() -> None:
    """
    🔥 Downgrade seguro:

    No eliminamos la columna porque fue creada en la migración base.
    Eliminarla rompería consistencia del esquema.
    """

    # NO HACER NADA
    pass