from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Participant(Base):
    __tablename__ = "participants"

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

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    initial_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("100.00"),
        nullable=False,
    )

    # Marks whether this participant is currently taking part in
    # unused for as long as they stay inactive).
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # =========================================================
    # ACCOUNT
    # =========================================================

    account = relationship(
        "Account",
        back_populates="participants",
    )

    # =========================================================
    # RELATIONSHIPS
    # =========================================================

    outgoing_relationships = relationship(
        "Relationship",
        foreign_keys="Relationship.from_participant_id",
        back_populates="from_participant",
        cascade="all, delete-orphan",
    )

    incoming_relationships = relationship(
        "Relationship",
        foreign_keys="Relationship.to_participant_id",
        back_populates="to_participant",
        cascade="all, delete-orphan",
    )

    # =========================================================
    # CYCLE PARTICIPATION
    # =========================================================

    cycle_participations = relationship(
        "CycleParticipant",
        back_populates="participant",
        cascade="all, delete-orphan",
    )