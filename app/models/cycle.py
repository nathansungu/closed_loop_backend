import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Cycle(Base):
    __tablename__ = "cycles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

    # Per-account continuous sequence number (1, 2, 3...)
    cycle_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # =========================================================
    # ACCOUNT OWNERSHIP
    # =========================================================

    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # STATUS
    # =========================================================

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    # =========================================================
    # DATES
    # =========================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # =========================================================
    # ACCOUNT
    # =========================================================

    account = relationship(
        "Account",
        back_populates="cycles",
    )

    # =========================================================
    # PARTICIPANTS
    # =========================================================

    participants = relationship(
        "CycleParticipant",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )

    # =========================================================
    # TRANSACTIONS
    # =========================================================

    transactions = relationship(
        "Transaction",
        back_populates="cycle",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "cycle_number",
            name="unique_account_cycle_number",
        ),
    )
