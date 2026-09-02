"""add is_active to accounts

Revision ID: a1b2c3d4e5f6
Revises: 9e4f2b1c3d5a
Create Date: 2026-09-02 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9e4f2b1c3d5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'accounts',
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.text('1'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('accounts', 'is_active')
