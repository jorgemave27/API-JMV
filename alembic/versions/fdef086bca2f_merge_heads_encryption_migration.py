"""merge heads encryption migration

Revision ID: fdef086bca2f
Revises: a632b9058035, f5ede326db53
Create Date: 2026-03-14 20:43:32.894667

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fdef086bca2f'
down_revision: Union[str, Sequence[str], None] = ('a632b9058035', 'f5ede326db53')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
