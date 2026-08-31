import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

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

    cycle_id: Mapped[int] = mapped_column(
        ForeignKey(
            "cycles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    from_participant_id: Mapped[int] = mapped_column(
        ForeignKey(
            "participants.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    to_participant_id: Mapped[int] = mapped_column(
        ForeignKey(
            "participants.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )

    round: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    cycle = relationship(
        "Cycle",
        back_populates="transactions",
    )

    from_participant = relationship(
        "Participant",
        foreign_keys=[from_participant_id],
    )

    to_participant = relationship(
        "Participant",
        foreign_keys=[to_participant_id],
    )
