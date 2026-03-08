from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e0c73d37628a"
down_revision = "12dd7c0c57ff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "configuracion_cors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("origin", sa.String(length=255), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_configuracion_cors_id"), "configuracion_cors", ["id"], unique=False)
    op.create_index(op.f("ix_configuracion_cors_origin"), "configuracion_cors", ["origin"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_configuracion_cors_origin"), table_name="configuracion_cors")
    op.drop_index(op.f("ix_configuracion_cors_id"), table_name="configuracion_cors")
    op.drop_table("configuracion_cors")