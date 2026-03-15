"""
add encrypted rfc to usuario
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "f5ede326db53"
down_revision = "6248ee81e571"
branch_labels = None
depends_on = None

def upgrade():
    """
    Agrega columna RFC cifrada al modelo Usuario.
    El cifrado ocurre a nivel aplicación (TypeDecorator).
    """
    op.add_column(
        "usuarios",
        sa.Column(
            "rfc",
            sa.String(length=255),
            nullable=True
        )
    )


def downgrade():
    """
    Reversión de la migración.
    """
    op.drop_column("usuarios", "rfc")