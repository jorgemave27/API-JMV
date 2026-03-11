"""crear tabla configuracion cors"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e0c73d37628a"
down_revision = "12dd7c0c57ff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Crea la tabla de configuración dinámica de CORS.

    Nota:
    - En PostgreSQL los booleanos no deben usar DEFAULT 1/0
    - Deben usar true/false
    """
    op.create_table(
        "configuracion_cors",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("origin", sa.String(length=255), nullable=False),
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
    )


def downgrade() -> None:
    """
    Elimina la tabla de configuración CORS.
    """
    op.drop_table("configuracion_cors")