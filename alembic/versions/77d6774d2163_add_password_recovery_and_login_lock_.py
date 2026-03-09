"""add password recovery and login lock fields to usuarios"""

from alembic import op
import sqlalchemy as sa


revision = "77d6774d2163"
down_revision = "c6ea1aa925a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usuarios",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "usuarios",
        sa.Column("blocked_until", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "usuarios",
        sa.Column("reset_token_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "usuarios",
        sa.Column("reset_token_expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "usuarios",
        sa.Column("reset_token_used_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usuarios", "reset_token_used_at")
    op.drop_column("usuarios", "reset_token_expires_at")
    op.drop_column("usuarios", "reset_token_hash")
    op.drop_column("usuarios", "blocked_until")
    op.drop_column("usuarios", "failed_login_attempts")