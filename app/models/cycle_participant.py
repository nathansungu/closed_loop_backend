from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CycleParticipant(Base):
    __tablename__ = "cycle_participants"

    __table_args__ = (
        UniqueConstraint(
            "cycle_id",
            "participant_id",
            name="unique_cycle_participant",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # =========================================================
    # CYCLE
    # =========================================================

    cycle_id: Mapped[int] = mapped_column(
        ForeignKey(
            "cycles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # =========================================================
    # PARTICIPANT
    # =========================================================

    participant_id: Mapped[int] = mapped_column(
        ForeignKey(
            "participants.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # =========================================================
    # INITIAL AMOUNT
    # =========================================================

    initial_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )

    # =========================================================
    # RELATIONSHIPS
    # =========================================================

    cycle = relationship(
        "Cycle",
        back_populates="participants",
    )

    participant = relationship(
        "Participant",
        back_populates="cycle_participations",
    )
