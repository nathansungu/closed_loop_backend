"""add email verification to users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-03 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = '2db4bc4ae03b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns for email verification
    op.add_column(
        'users',
        sa.Column(
            'is_verified',
            sa.Boolean(),
            server_default=sa.text('0'),
            nullable=False,
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'verification_code',
            sa.String(length=6),
            nullable=True,
        ),
    )
    op.add_column(
        'users',
        sa.Column(
            'verification_code_expires_at',
            sa.DateTime(),
            nullable=True,
        ),
    )

    # Backfill existing users as verified
    op.execute("UPDATE users SET is_verified = 1 WHERE is_verified = 0")


def downgrade() -> None:
    op.drop_column('users', 'verification_code_expires_at')
    op.drop_column('users', 'verification_code')
    op.drop_column('users', 'is_verified')
