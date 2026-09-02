"""add cycle_number to cycles

Revision ID: 9e4f2b1c3d5a
Revises: 8d3c5f1b2e4a
Create Date: 2026-09-02 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '9e4f2b1c3d5a'
down_revision: Union[str, Sequence[str], None] = '8d3c5f1b2e4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add cycle_number, backfill per-account sequence, and add unique constraint."""
    conn = op.get_bind()

    # 1. Add column
    op.add_column(
        'cycles',
        sa.Column(
            'cycle_number',
            sa.Integer(),
            nullable=True,
        ),
    )

    # 2. Backfill existing cycle numbers per account (1, 2, 3...)
    account_rows = conn.execute(text("SELECT DISTINCT account_id FROM cycles")).fetchall()
    for (acc_id,) in account_rows:
        cycle_rows = conn.execute(
            text("SELECT id FROM cycles WHERE account_id = :acc_id ORDER BY id ASC"),
            {"acc_id": acc_id},
        ).fetchall()
        for idx, (cyc_id,) in enumerate(cycle_rows, start=1):
            conn.execute(
                text("UPDATE cycles SET cycle_number = :seq WHERE id = :cyc_id"),
                {"seq": idx, "cyc_id": cyc_id},
            )

    # 3. Alter column to NOT NULL with default 1
    op.alter_column(
        'cycles',
        'cycle_number',
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text('1'),
    )

    # 4. Add unique constraint on (account_id, cycle_number)
    op.create_unique_constraint(
        'unique_account_cycle_number',
        'cycles',
        ['account_id', 'cycle_number'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('unique_account_cycle_number', 'cycles', type_='unique')
    op.drop_column('cycles', 'cycle_number')
