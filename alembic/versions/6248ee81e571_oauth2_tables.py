"""oauth2 tables

Revision ID: 6248ee81e571
Revises: 0b42d0f2d8ef
Create Date: 2026-03-13 19:03:43.825482

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6248ee81e571"
down_revision: Union[str, Sequence[str], None] = "0b42d0f2d8ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------
    # Tabla de clientes OAuth registrados
    # -----------------------------------------------------
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("redirect_uris", sa.JSON(), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oauth_clients_client_id"),
        "oauth_clients",
        ["client_id"],
        unique=True,
    )

    # -----------------------------------------------------
    # Tabla de refresh tokens OAuth
    # -----------------------------------------------------
    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=True),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("client_id", sa.String(length=255), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oauth_refresh_tokens_token"),
        "oauth_refresh_tokens",
        ["token"],
        unique=True,
    )
    op.create_index(
        op.f("ix_oauth_refresh_tokens_user_email"),
        "oauth_refresh_tokens",
        ["user_email"],
        unique=False,
    )


def downgrade() -> None:
    # -----------------------------------------------------
    # Rollback de OAuth refresh tokens
    # -----------------------------------------------------
    op.drop_index(
        op.f("ix_oauth_refresh_tokens_user_email"),
        table_name="oauth_refresh_tokens",
    )
    op.drop_index(
        op.f("ix_oauth_refresh_tokens_token"),
        table_name="oauth_refresh_tokens",
    )
    op.drop_table("oauth_refresh_tokens")

    # -----------------------------------------------------
    # Rollback de OAuth clients
    # -----------------------------------------------------
    op.drop_index(
        op.f("ix_oauth_clients_client_id"),
        table_name="oauth_clients",
    )
    op.drop_table("oauth_clients")
