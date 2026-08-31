from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Participant, Relationship, Account
from app.services.prediction_service import predict_cycles


class PredictionItem(BaseModel):
    period: int
    date: datetime
    outgoing_cycle: list[int]
    return_cycle: list[int]


router = APIRouter(
    prefix="/api/predictions",
    tags=["Predictions"],
)


@router.get("/account/{account_id}", response_model=list[PredictionItem])
def get_account_predictions(
    account_id: int,
    periods: int = Query(7, ge=1, le=365),
    start_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    participants = db.execute(
        select(Participant.id).where(Participant.account_id == account_id)
    ).scalars().all()

    if len(participants) < 5:
        raise HTTPException(
            status_code=400,
            detail="At least 5 participants are required for multi-period cycle predictions.",
        )

    p_set = set(participants)
    relationships = db.execute(
        select(Relationship).where(
            Relationship.from_participant_id.in_(p_set),
            Relationship.to_participant_id.in_(p_set),
        )
    ).scalars().all()

    predictions = predict_cycles(
        participant_ids=participants,
        relationships=relationships,
        periods=periods,
        start_date=start_date,
    )

    return [
        {
            "period": p.period,
            "date": p.date,
            "outgoing_cycle": p.outgoing_cycle,
            "return_cycle": p.return_cycle,
        }
        for p in predictions
    ]
