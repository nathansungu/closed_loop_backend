from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Relationship, Participant, Account
from app.models.user import User
from app.routers.auth import get_optional_current_user
from app.services.relationship_service import create_relationship


class RelationshipCreate(BaseModel):
    from_participant_id: int
    to_participant_id: int


class RelationshipResponse(BaseModel):
    id: int
    from_participant_id: int
    to_participant_id: int
    times_used: int
    first_used_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/relationships",
    tags=["Relationships"],
)


@router.get("/account/{account_id}", response_model=list[RelationshipResponse])
def get_relationships_by_account(
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
            detail="Access denied: You cannot view relationships belonging to another organization.",
        )

    participants = db.execute(
        select(Participant.id).where(Participant.account_id == account_id)
    ).scalars().all()
    
    if not participants:
        return []

    p_set = set(participants)
    result = db.execute(
        select(Relationship).where(
            Relationship.from_participant_id.in_(p_set),
            Relationship.to_participant_id.in_(p_set),
        ).order_by(Relationship.id)
    )
    return result.scalars().all()


@router.post("/", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
def add_relationship(
    data: RelationshipCreate,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    from_p = db.get(Participant, data.from_participant_id)
    to_p = db.get(Participant, data.to_participant_id)

    if not from_p or not to_p:
        raise HTTPException(status_code=404, detail="One or both participants not found")

    if from_p.account_id != to_p.account_id:
        raise HTTPException(
            status_code=400,
            detail="Relationships can only be created between participants of the same account",
        )

    account = db.get(Account, from_p.account_id)
    if current_user and current_user.account_id != from_p.account_id and (not account or account.owner_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot create relationships in another organization.",
        )

    try:
        rel = create_relationship(
            db=db,
            from_participant_id=data.from_participant_id,
            to_participant_id=data.to_participant_id,
        )
        return rel
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/account/{account_id}/auto-ring", response_model=list[RelationshipResponse], status_code=status.HTTP_201_CREATED)
def auto_create_directed_ring(account_id: int, db: Session = Depends(get_db)):
    """
    Convenience helper that extends the directed relationship network toward
    a full tournament among the account's participants.

    Existing relationships (and their usage stats) are left completely
    untouched — this only fills in pairs that don't yet have an edge in
    either direction, which is exactly what's needed when new participants
    are added and the network is regenerated.
    """
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    participants = db.execute(
        select(Participant.id).where(Participant.account_id == account_id).order_by(Participant.id)
    ).scalars().all()

    if len(participants) < 5:
        raise HTTPException(
            status_code=400,
            detail=f"At least 5 participants are required to form a valid directed cycle network (currently {len(participants)}).",
        )

    p_set = set(participants)

    # Load existing relationships WITHOUT deleting them — we want to keep
    # every already-established edge (and its usage stats) exactly as-is.
    existing_rels = db.execute(
        select(Relationship).where(
            Relationship.from_participant_id.in_(p_set),
            Relationship.to_participant_id.in_(p_set),
        )
    ).scalars().all()

    # Track pairs that already have an edge in EITHER direction, so we
    # never touch them and never create a reverse of an existing edge.
    covered_pairs: set[frozenset[int]] = {
        frozenset((rel.from_participant_id, rel.to_participant_id))
        for rel in existing_rels
    }

    n = len(participants)
    created_edges: set[tuple[int, int]] = set()

    def try_add_edge(from_id: int, to_id: int) -> None:
        if from_id == to_id:
            return
        pair = frozenset((from_id, to_id))
        if pair in covered_pairs:
            return  # already exists (either direction) — leave it alone
        if (to_id, from_id) in created_edges:
            return  # reverse already queued this run — skip
        created_edges.add((from_id, to_id))
        covered_pairs.add(pair)

    # Same full-tournament coverage as before, but now only for pairs that
    # aren't already covered by an existing relationship.
    for offset in range(1, (n // 2) + 1):
        for i in range(n):
            try_add_edge(participants[i], participants[(i + offset) % n])

    created_relationships = []
    for from_id, to_id in created_edges:
        rel = Relationship(
            from_participant_id=from_id,
            to_participant_id=to_id,
            times_used=0,
        )
        db.add(rel)
        created_relationships.append(rel)

    db.commit()
    for rel in created_relationships:
        db.refresh(rel)

    return created_relationships

@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(relationship_id: int, db: Session = Depends(get_db)):
    rel = db.get(Relationship, relationship_id)
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")
    db.delete(rel)
    db.commit()
    return None