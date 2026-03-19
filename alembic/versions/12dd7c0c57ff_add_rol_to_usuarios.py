"""add rol to usuarios

Revision ID: 12dd7c0c57ff
Revises: 9869a419cf96
Create Date: 2026-03-07

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "12dd7c0c57ff"
down_revision = "9869a419cf96"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column(
            "rol",
            sa.String(length=50),
            nullable=False,
            server_default="lector",
        ),
    )


def downgrade() -> None:
    op.drop_column("usuarios", "rol")
