"""merge heads

Revision ID: c115be606beb
Revises: b0b86b633e49, add_print_marketplace_02
Create Date: 2026-09-17 13:09:50.038114

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c115be606beb'
down_revision: Union[str, Sequence[str], None] = ('b0b86b633e49', 'add_print_marketplace_02')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
