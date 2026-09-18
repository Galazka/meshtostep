"""merge_pricing_and_baseline_heads

Revision ID: 38596f19a5fc
Revises: add_pricing_v4, c115be606beb
Create Date: 2026-09-18 15:14:23.789748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38596f19a5fc'
down_revision: Union[str, Sequence[str], None] = ('add_pricing_v4', 'c115be606beb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
