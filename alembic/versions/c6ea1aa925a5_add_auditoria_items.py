"""add auditoria_items"""

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

    Nota:
    - No se intenta borrar ix_configuracion_cors_id porque en PostgreSQL
      ese índice no existe como índice independiente; el PRIMARY KEY ya
      cubre la columna id.
    """
    op.create_table(
        "auditoria_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("accion", sa.String(length=50), nullable=False),
        sa.Column("datos_anteriores", sa.JSON(), nullable=True),
        sa.Column("datos_nuevos", sa.JSON(), nullable=True),
        sa.Column("usuario", sa.String(length=255), nullable=True),
        sa.Column(
            "activo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "creado_en",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
    )

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
        "ix_auditoria_items_creado_en",
        "auditoria_items",
        ["creado_en"],
        unique=False,
    )


def downgrade() -> None:
    """
    Elimina la tabla de auditoría de items.
    """
    op.drop_index("ix_auditoria_items_creado_en", table_name="auditoria_items")
    op.drop_index("ix_auditoria_items_accion", table_name="auditoria_items")
    op.drop_index("ix_auditoria_items_item_id", table_name="auditoria_items")
    op.drop_table("auditoria_items")