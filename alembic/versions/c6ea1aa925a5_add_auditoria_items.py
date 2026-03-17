"""add auditoria_items (SQLITE SAFE + PROD READY)"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c6ea1aa925a5"
down_revision = "e0c73d37628a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Crea la tabla de auditoría de items.

    🔥 Compatible con SQLite y PostgreSQL
    🔥 Sin funciones SQL no soportadas (now())
    🔥 Defaults manejados desde Python
    """

    op.create_table(
        "auditoria_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),

        # referencia al item
        sa.Column("item_id", sa.Integer(), nullable=False),

        # acción (CREATE, UPDATE, DELETE)
        sa.Column("accion", sa.String(length=20), nullable=False),

        # snapshots
        sa.Column("datos_anteriores", sa.JSON(), nullable=True),
        sa.Column("datos_nuevos", sa.JSON(), nullable=True),

        # usuario responsable (ajustado a tu modelo actual)
        sa.Column("usuario_id", sa.Integer(), nullable=True),

        # 🔥 eliminado "activo" (no lo estás usando en el modelo actual)

        # 🔥 timestamp SIN server_default (lo maneja Python)
        sa.Column("timestamp", sa.DateTime(), nullable=True),

        # 🔥 ip cliente
        sa.Column("ip_cliente", sa.String(length=64), nullable=True),

        # FK
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
    )

    # índices
    op.create_index(
        "ix_auditoria_items_item_id",
        "auditoria_items",
        ["item_id"],
        unique=False,
    )

    op.create_index(
        "ix_auditoria_items_accion",
        "auditoria_items",
        ["accion"],
        unique=False,
    )

    op.create_index(
        "ix_auditoria_items_timestamp",
        "auditoria_items",
        ["timestamp"],
        unique=False,
    )


def downgrade() -> None:
    """
    Elimina la tabla de auditoría de items.
    """

    op.drop_index("ix_auditoria_items_timestamp", table_name="auditoria_items")
    op.drop_index("ix_auditoria_items_accion", table_name="auditoria_items")
    op.drop_index("ix_auditoria_items_item_id", table_name="auditoria_items")
    op.drop_table("auditoria_items")