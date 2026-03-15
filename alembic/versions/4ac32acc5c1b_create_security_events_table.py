from alembic import op
import sqlalchemy as sa


revision = "security_events_table"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    op.create_table(
        "security_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("tipo_evento", sa.String(length=50), nullable=False),
        sa.Column("detalles", sa.Text(), nullable=False),
        sa.Column("accion_tomada", sa.String(length=50), nullable=False),
        sa.Column("pais", sa.String(length=10), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_security_events_ip", "security_events", ["ip"])
    op.create_index("ix_security_events_timestamp", "security_events", ["timestamp"])


def downgrade():

    op.drop_index("ix_security_events_timestamp", table_name="security_events")
    op.drop_index("ix_security_events_ip", table_name="security_events")
    op.drop_table("security_events")
