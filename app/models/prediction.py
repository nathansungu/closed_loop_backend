from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    cycle_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    prediction_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    outgoing_cycle: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    return_cycle: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    confidence: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
