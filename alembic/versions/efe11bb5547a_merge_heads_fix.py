"""merge heads fix

Revision ID: efe11bb5547a
Revises: 6c5ce50a097c
Create Date: 2026-03-17 16:06:01.356030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'efe11bb5547a'
down_revision: Union[str, Sequence[str], None] = '6c5ce50a097c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
