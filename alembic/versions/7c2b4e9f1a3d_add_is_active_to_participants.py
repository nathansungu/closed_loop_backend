"""add is_active to participants

Revision ID: 7c2b4e9f1a3d
Revises: 239da014a9b1
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c2b4e9f1a3d'
down_revision: Union[str, Sequence[str], None] = '239da014a9b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'participants',
        sa.Column(
            'is_active',
            sa.Boolean(),
            server_default=sa.text('1'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('participants', 'is_active')
