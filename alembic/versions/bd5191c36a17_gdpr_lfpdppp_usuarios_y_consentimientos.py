"""gdpr lfpdppp usuarios y consentimientos

Revision ID: bd5191c36a17
Revises: fdef086bca2f
Create Date: 2026-03-16
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "bd5191c36a17"
down_revision = "fdef086bca2f"
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)

    if table_name not in inspector.get_table_names():
        return False

    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)

    if table_name not in inspector.get_table_names():
        return False

    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    if table_exists("usuarios"):
        if not column_exists("usuarios", "consentimiento_datos"):
            op.add_column(
                "usuarios",
                sa.Column(
                    "consentimiento_datos",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )

        if not column_exists("usuarios", "fecha_consentimiento"):
            op.add_column(
                "usuarios",
                sa.Column("fecha_consentimiento", sa.DateTime(), nullable=True),
            )

        if not column_exists("usuarios", "origen_consentimiento"):
            op.add_column(
                "usuarios",
                sa.Column("origen_consentimiento", sa.String(length=100), nullable=True),
            )

        if not column_exists("usuarios", "anonimizado"):
            op.add_column(
                "usuarios",
                sa.Column(
                    "anonimizado",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )

        if not column_exists("usuarios", "fecha_anonimizacion"):
            op.add_column(
                "usuarios",
                sa.Column("fecha_anonimizacion", sa.DateTime(), nullable=True),
            )

        if not column_exists("usuarios", "motivo_anonimizacion"):
            op.add_column(
                "usuarios",
                sa.Column("motivo_anonimizacion", sa.String(length=255), nullable=True),
            )

        if not column_exists("usuarios", "solicitud_arco_tipo"):
            op.add_column(
                "usuarios",
                sa.Column("solicitud_arco_tipo", sa.String(length=50), nullable=True),
            )

        if not column_exists("usuarios", "solicitud_arco_fecha"):
            op.add_column(
                "usuarios",
                sa.Column("solicitud_arco_fecha", sa.DateTime(), nullable=True),
            )

        if not column_exists("usuarios", "solicitud_arco_estatus"):
            op.add_column(
                "usuarios",
                sa.Column("solicitud_arco_estatus", sa.String(length=50), nullable=True),
            )

        if not index_exists("usuarios", "ix_usuarios_anonimizado"):
            op.create_index(
                "ix_usuarios_anonimizado",
                "usuarios",
                ["anonimizado"],
                unique=False,
            )

    if not table_exists("consentimientos_datos_personales"):
        op.create_table(
            "consentimientos_datos_personales",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("usuario_id", sa.Integer(), nullable=False),
            sa.Column("tipo_consentimiento", sa.String(length=100), nullable=False),
            sa.Column(
                "otorgado",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("fecha_otorgado", sa.DateTime(), nullable=True),
            sa.Column("version_aviso_privacidad", sa.String(length=50), nullable=True),
            sa.Column("origen", sa.String(length=100), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        )

        op.create_index(
            "ix_consentimientos_datos_personales_usuario_id",
            "consentimientos_datos_personales",
            ["usuario_id"],
            unique=False,
        )

    if not table_exists("solicitudes_arco"):
        op.create_table(
            "solicitudes_arco",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("usuario_id", sa.Integer(), nullable=False),
            sa.Column("tipo", sa.String(length=50), nullable=False),
            sa.Column(
                "estatus",
                sa.String(length=50),
                nullable=False,
                server_default="pendiente",
            ),
            sa.Column("detalle", sa.Text(), nullable=True),
            sa.Column(
                "fecha_solicitud",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("fecha_resolucion", sa.DateTime(), nullable=True),
            sa.Column("respuesta", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        )

        op.create_index(
            "ix_solicitudes_arco_usuario_id",
            "solicitudes_arco",
            ["usuario_id"],
            unique=False,
        )

        op.create_index(
            "ix_solicitudes_arco_estatus",
            "solicitudes_arco",
            ["estatus"],
            unique=False,
        )


def downgrade() -> None:
    if table_exists("solicitudes_arco"):
        if index_exists("solicitudes_arco", "ix_solicitudes_arco_estatus"):
            op.drop_index("ix_solicitudes_arco_estatus", table_name="solicitudes_arco")
        if index_exists("solicitudes_arco", "ix_solicitudes_arco_usuario_id"):
            op.drop_index("ix_solicitudes_arco_usuario_id", table_name="solicitudes_arco")
        op.drop_table("solicitudes_arco")

    if table_exists("consentimientos_datos_personales"):
        if index_exists(
            "consentimientos_datos_personales",
            "ix_consentimientos_datos_personales_usuario_id",
        ):
            op.drop_index(
                "ix_consentimientos_datos_personales_usuario_id",
                table_name="consentimientos_datos_personales",
            )
        op.drop_table("consentimientos_datos_personales")

    if table_exists("usuarios"):
        if index_exists("usuarios", "ix_usuarios_anonimizado"):
            op.drop_index("ix_usuarios_anonimizado", table_name="usuarios")

        for column_name in [
            "solicitud_arco_estatus",
            "solicitud_arco_fecha",
            "solicitud_arco_tipo",
            "motivo_anonimizacion",
            "fecha_anonimizacion",
            "anonimizado",
            "origen_consentimiento",
            "fecha_consentimiento",
            "consentimiento_datos",
        ]:
            if column_exists("usuarios", column_name):
                op.drop_column("usuarios", column_name)
