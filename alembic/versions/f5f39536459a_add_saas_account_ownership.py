from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f5f39536459a"
down_revision: Union[str, Sequence[str], None] = "a80c39c3afd6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add SaaS account ownership safely.

    Existing participants and cycles are assigned to a
    default account so existing data is preserved.
    """

    # --------------------------------------------------
    # 1. Create accounts table
    # --------------------------------------------------

    op.create_table(
        "accounts",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "uuid",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "uuid",
            name="uq_accounts_uuid",
        ),
    )

    # --------------------------------------------------
    # 2. Create a default account for existing data
    # --------------------------------------------------

    accounts_table = sa.table(
        "accounts",
        sa.column("id", sa.Integer),
        sa.column("uuid", sa.String),
        sa.column("name", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    connection = op.get_bind()

    connection.execute(
        accounts_table.insert().values(
            uuid="00000000-0000-0000-0000-000000000001",
            name="Default Account",
            created_at=sa.func.now(),
            updated_at=sa.func.now(),
        )
    )

    default_account_id = connection.execute(sa.text("""
            SELECT id
            FROM accounts
            WHERE uuid = '00000000-0000-0000-0000-000000000001'
            LIMIT 1
            """)).scalar_one()

    # --------------------------------------------------
    # 3. Add account_id to participants
    #
    # Temporarily nullable so existing records can
    # be assigned the default account.
    # --------------------------------------------------

    op.add_column(
        "participants",
        sa.Column(
            "account_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_participants_account_id",
        "participants",
        ["account_id"],
        unique=False,
    )

    # --------------------------------------------------
    # 4. Assign existing participants to default account
    # --------------------------------------------------

    connection.execute(
        sa.text("""
            UPDATE participants
            SET account_id = :account_id
            WHERE account_id IS NULL
            """),
        {
            "account_id": default_account_id,
        },
    )

    # --------------------------------------------------
    # 5. Make participant ownership mandatory
    # --------------------------------------------------

    op.alter_column(
        "participants",
        "account_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # --------------------------------------------------
    # 6. Add participant foreign key
    # --------------------------------------------------

    op.create_foreign_key(
        "fk_participants_account_id",
        "participants",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --------------------------------------------------
    # 7. Add account_id to cycles
    #
    # Temporarily nullable for existing cycles.
    # --------------------------------------------------

    op.add_column(
        "cycles",
        sa.Column(
            "account_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_cycles_account_id",
        "cycles",
        ["account_id"],
        unique=False,
    )

    # --------------------------------------------------
    # 8. Assign existing cycles to default account
    # --------------------------------------------------

    connection.execute(
        sa.text("""
            UPDATE cycles
            SET account_id = :account_id
            WHERE account_id IS NULL
            """),
        {
            "account_id": default_account_id,
        },
    )

    # --------------------------------------------------
    # 9. Make cycle ownership mandatory
    # --------------------------------------------------

    op.alter_column(
        "cycles",
        "account_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # --------------------------------------------------
    # 10. Add cycle foreign key
    # --------------------------------------------------

    op.create_foreign_key(
        "fk_cycles_account_id",
        "cycles",
        "accounts",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --------------------------------------------------
    # 11. Preserve existing indexes
    #
    # Only create these if they don't already exist.
    # --------------------------------------------------

    op.create_index(
        "ix_cycles_created_at",
        "cycles",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_cycles_status",
        "cycles",
        ["status"],
        unique=False,
    )

    # --------------------------------------------------
    # IMPORTANT:
    #
    # We intentionally DO NOT drop the predictions table.
    #
    # Alembic detected it as removed because the Prediction
    # model is no longer registered in Base.metadata.
    #
    # Existing database data should not be destroyed by this
    # SaaS migration.
    # --------------------------------------------------


def downgrade() -> None:
    """
    Reverse SaaS account ownership changes.

    Existing predictions are preserved.
    """

    # --------------------------------------------------
    # Remove cycles foreign key/index
    # --------------------------------------------------

    op.drop_constraint(
        "fk_cycles_account_id",
        "cycles",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_cycles_account_id",
        table_name="cycles",
    )

    op.drop_index(
        "ix_cycles_created_at",
        table_name="cycles",
    )

    op.drop_index(
        "ix_cycles_status",
        table_name="cycles",
    )

    op.drop_column(
        "cycles",
        "account_id",
    )

    # --------------------------------------------------
    # Remove participants foreign key/index
    # --------------------------------------------------

    op.drop_constraint(
        "fk_participants_account_id",
        "participants",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_participants_account_id",
        table_name="participants",
    )

    op.drop_column(
        "participants",
        "account_id",
    )

    # --------------------------------------------------
    # Remove accounts table
    # --------------------------------------------------

    op.drop_table("accounts")
