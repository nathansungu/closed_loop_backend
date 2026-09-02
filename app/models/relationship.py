from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    from_participant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )

    to_participant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
    )

    first_used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    times_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    from_participant = relationship(
        "Participant",
        foreign_keys=[from_participant_id],
        back_populates="outgoing_relationships",
    )

    to_participant = relationship(
        "Participant",
        foreign_keys=[to_participant_id],
        back_populates="incoming_relationships",
    )

    __table_args__ = (
        UniqueConstraint(
            "from_participant_id",
            "to_participant_id",
            name="unique_relationship",
        ),
        CheckConstraint(
            "from_participant_id <> to_participant_id",
            name="no_self_relationship",
        ),
    )
