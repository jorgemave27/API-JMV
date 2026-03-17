"""add usuario_id to auditoria_items

Revision ID: 6c5ce50a097c
Revises: bd5191c36a17
Create Date: 2026-03-17 13:40:09.922316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c5ce50a097c'
down_revision: Union[str, Sequence[str], None] = 'bd5191c36a17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.add_column(
        'auditoria_items',
        sa.Column('usuario_id', sa.Integer(), nullable=True)
    )

def downgrade():
    op.drop_column('auditoria_items', 'usuario_id')