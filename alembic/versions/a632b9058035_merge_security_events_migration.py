"""merge security events migration

Revision ID: a632b9058035
Revises: security_events_table, 6248ee81e571
Create Date: 2026-03-14 15:10:11.701287

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "a632b9058035"
down_revision: Union[str, Sequence[str], None] = ("security_events_table", "6248ee81e571")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
