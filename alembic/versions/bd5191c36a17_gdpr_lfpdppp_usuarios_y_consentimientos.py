"""gdpr lfpdppp usuarios y consentimientos

Revision ID: bd5191c36a17
Revises: fdef086bca2f
Create Date: 2026-03-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bd5191c36a17"
down_revision: Union[str, Sequence[str], None] = "fdef086bca2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------
# helpers sqlite
# ---------------------------------------------------------

def column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    cols = [row[1] for row in result]
    return column in cols


def table_exists(table: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
        ),
        {"t": table},
    ).fetchone()

    return result is not None


# ---------------------------------------------------------
# upgrade
# ---------------------------------------------------------

def upgrade() -> None:

    # ---------------------------------------------------------
    # usuarios.nombre
    # ---------------------------------------------------------

    if not column_exists("usuarios", "nombre"):
        op.add_column(
            "usuarios",
            sa.Column(
                "nombre",
                sa.String(length=255),
                nullable=True,
            ),
        )

    # ---------------------------------------------------------
    # usuarios.updated_at
    # ---------------------------------------------------------

    if not column_exists("usuarios", "updated_at"):

        op.add_column(
            "usuarios",
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=True,
            ),
        )

        op.execute(
            """
            UPDATE usuarios
            SET updated_at = CURRENT_TIMESTAMP
            """
        )

    # ---------------------------------------------------------
    # usuarios.ultimo_acceso_at
    # ---------------------------------------------------------

    if not column_exists("usuarios", "ultimo_acceso_at"):
        op.add_column(
            "usuarios",
            sa.Column(
                "ultimo_acceso_at",
                sa.DateTime(),
                nullable=True,
            ),
        )

    # ---------------------------------------------------------
    # consentimientos_privacidad
    # ---------------------------------------------------------

    if not table_exists("consentimientos_privacidad"):

        op.create_table(
            "consentimientos_privacidad",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("usuario_id", sa.Integer(), nullable=False),
            sa.Column("version_aviso", sa.String(length=50), nullable=False),
            sa.Column("ip_cliente", sa.String(length=45), nullable=False),
            sa.Column(
                "fecha_aceptacion",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
            ),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

        op.create_index(
            "ix_consentimientos_privacidad_usuario_id",
            "consentimientos_privacidad",
            ["usuario_id"],
        )


# ---------------------------------------------------------
# downgrade
# ---------------------------------------------------------

def downgrade() -> None:

    if table_exists("consentimientos_privacidad"):

        op.drop_index(
            "ix_consentimientos_privacidad_usuario_id",
            table_name="consentimientos_privacidad",
        )

        op.drop_table("consentimientos_privacidad")

    if column_exists("usuarios", "ultimo_acceso_at"):
        op.drop_column("usuarios", "ultimo_acceso_at")

    if column_exists("usuarios", "updated_at"):
        op.drop_column("usuarios", "updated_at")

    if column_exists("usuarios", "nombre"):
        op.drop_column("usuarios", "nombre")