from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account
from app.models.participant import Participant
from app.models.user import User
from app.routers.auth import get_optional_current_user


class ParticipantCreate(BaseModel):
    account_id: int
    name: str
    initial_amount: Decimal | None = Decimal("100.00")


class ParticipantUpdate(BaseModel):
    name: str | None = None
    initial_amount: Decimal | None = None
    is_active: bool | None = None


class ParticipantResponse(BaseModel):
    id: int
    uuid: str
    account_id: int
    name: str
    initial_amount: Decimal
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/api/participants",
    tags=["Participants"],
)


@router.get("/account/{account_id}", response_model=list[ParticipantResponse])
def get_account_participants(
    account_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if current_user and current_user.account_id != account_id and account.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot view participants belonging to another organization.",
        )
    result = db.execute(
        select(Participant).where(Participant.account_id == account_id).order_by(Participant.id)
    )
    return result.scalars().all()


@router.post("/", response_model=ParticipantResponse, status_code=status.HTTP_201_CREATED)
def create_participant(
    data: ParticipantCreate,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    account = db.get(Account, data.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if current_user and current_user.account_id != data.account_id and account.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot create participants in another organization.",
        )
    
    clean_name = data.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Participant name cannot be empty")

    existing = db.execute(
        select(Participant).where(
            Participant.account_id == data.account_id,
            func.lower(Participant.name) == clean_name.lower(),
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A participant named '{clean_name}' already exists in this account.",
        )
    
    participant = Participant(
        account_id=data.account_id,
        name=clean_name,
        initial_amount=data.initial_amount if data.initial_amount is not None else Decimal("100.00"),
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


@router.get("/{participant_id}", response_model=ParticipantResponse)
def get_participant(participant_id: int, db: Session = Depends(get_db)):
    participant = db.get(Participant, participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    return participant


@router.put("/{participant_id}", response_model=ParticipantResponse)
def update_participant(participant_id: int, data: ParticipantUpdate, db: Session = Depends(get_db)):
    participant = db.get(Participant, participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    if data.name is not None:
        clean_name = data.name.strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="Participant name cannot be empty")
        
        existing = db.execute(
            select(Participant).where(
                Participant.account_id == participant.account_id,
                Participant.id != participant.id,
                func.lower(Participant.name) == clean_name.lower(),
            )
        ).scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"A participant named '{clean_name}' already exists in this account.",
            )
        participant.name = clean_name

    if data.initial_amount is not None:
        if data.initial_amount < 0:
            raise HTTPException(status_code=400, detail="Initial amount cannot be negative")
        participant.initial_amount = data.initial_amount

    if data.is_active is not None:
        participant.is_active = data.is_active

    db.commit()
    db.refresh(participant)
    return participant


@router.delete("/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_participant(participant_id: int, db: Session = Depends(get_db)):
    participant = db.get(Participant, participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    db.delete(participant)
    db.commit()
    return None

