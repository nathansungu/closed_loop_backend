"""add is_active to relationships

Revision ID: 8d3c5f1b2e4a
Revises: 7c2b4e9f1a3d
Create Date: 2026-09-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8d3c5f1b2e4a'
down_revision: Union[str, Sequence[str], None] = '7c2b4e9f1a3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'relationships',
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.text('1'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('relationships', 'is_active')
