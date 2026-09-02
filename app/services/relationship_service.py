from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Participant, Relationship


def get_relationship(
    db: Session,
    relationship_id: int,
) -> Relationship | None:
  
    return db.get(
        Relationship,
        relationship_id,
    )


def get_all_relationships(
    db: Session,
) -> list[Relationship]:
  

    result = db.execute(
        select(Relationship).order_by(
            Relationship.id.asc(),
        )
    )

    return list(result.scalars().all())


def get_relationships_for_participant(
    db: Session,
    participant_id: int,
) -> list[Relationship]:
   

    result = db.execute(
        select(Relationship)
        .where(
            Relationship.from_participant_id == participant_id,
        )
        .order_by(
            Relationship.id.asc(),
        )
    )

    return list(result.scalars().all())


def get_incoming_relationships(
    db: Session,
    participant_id: int,
) -> list[Relationship]:
  

    result = db.execute(
        select(Relationship)
        .where(
            Relationship.to_participant_id == participant_id,
        )
        .order_by(
            Relationship.id.asc(),
        )
    )

    return list(result.scalars().all())


def relationship_exists(
    db: Session,
    from_participant_id: int,
    to_participant_id: int,
) -> Relationship | None:
 
    result = db.execute(
        select(Relationship).where(
            Relationship.from_participant_id == from_participant_id,
            Relationship.to_participant_id == to_participant_id,
        )
    )

    return result.scalar_one_or_none()


def reverse_relationship_exists(
    db: Session,
    from_participant_id: int,
    to_participant_id: int,
) -> Relationship | None:
   

    result = db.execute(
        select(Relationship).where(
            Relationship.from_participant_id == to_participant_id,
            Relationship.to_participant_id == from_participant_id,
        )
    )

    return result.scalar_one_or_none()


def validate_participants(
    db: Session,
    from_participant_id: int,
    to_participant_id: int,
) -> tuple[Participant, Participant]:
   

    if from_participant_id == to_participant_id:
        raise ValueError(
            "A participant cannot have a relationship with themselves."
        )

    from_participant = db.get(
        Participant,
        from_participant_id,
    )

    if from_participant is None:
        raise ValueError(
            f"Source participant {from_participant_id} was not found."
        )

    to_participant = db.get(
        Participant,
        to_participant_id,
    )

    if to_participant is None:
        raise ValueError(
            f"Destination participant {to_participant_id} was not found."
        )

    if from_participant.account_id != to_participant.account_id:
        raise ValueError(
            "Participants must belong to the same account."
        )

    return from_participant, to_participant


def create_relationship(
    db: Session,
    from_participant_id: int,
    to_participant_id: int,
) -> Relationship:
    

    # ---------------------------------------------------------
    # Validate participants
    # ---------------------------------------------------------

    validate_participants(
        db=db,
        from_participant_id=from_participant_id,
        to_participant_id=to_participant_id,
    )

    # ---------------------------------------------------------
    # Check exact relationship
    # ---------------------------------------------------------

    existing = relationship_exists(
        db=db,
        from_participant_id=from_participant_id,
        to_participant_id=to_participant_id,
    )

    if existing is not None:
        return existing

    # ---------------------------------------------------------
    # Check forbidden reverse relationship
    # ---------------------------------------------------------

    reverse = reverse_relationship_exists(
        db=db,
        from_participant_id=from_participant_id,
        to_participant_id=to_participant_id,
    )

    if reverse is not None:
        raise ValueError(
            "Reverse relationship is forbidden. "
            f"{to_participant_id} -> {from_participant_id} "
            "already exists, therefore "
            f"{from_participant_id} -> {to_participant_id} "
            "cannot be created."
        )

    # ---------------------------------------------------------
    # Create relationship
    # ---------------------------------------------------------

    relationship = Relationship(
        from_participant_id=from_participant_id,
        to_participant_id=to_participant_id,
        times_used=0,
        first_used_at=None,
        last_used_at=None,
    )

    db.add(relationship)

    try:
        db.commit()
        db.refresh(relationship)

    except IntegrityError:
        db.rollback()

        # A concurrent request may have created the relationship
        # between our existence check and commit.
        existing = relationship_exists(
            db=db,
            from_participant_id=from_participant_id,
            to_participant_id=to_participant_id,
        )

        if existing is not None:
            return existing

        reverse = reverse_relationship_exists(
            db=db,
            from_participant_id=from_participant_id,
            to_participant_id=to_participant_id,
        )

        if reverse is not None:
            raise ValueError(
                "Reverse relationship is forbidden."
            )

        raise

    return relationship


def delete_relationship(
    db: Session,
    relationship_id: int,
) -> bool:
   
    relationship = get_relationship(
        db=db,
        relationship_id=relationship_id,
    )

    if relationship is None:
        raise ValueError(
            "Relationship not found."
        )

    times_used = relationship.times_used or 0

    if times_used > 0:
        raise ValueError(
            "A relationship that has already been used by a cycle "
            "cannot be deleted."
        )

    db.delete(relationship)
    db.commit()

    return True


def validate_relationship(
    db: Session,
    from_participant_id: int,
    to_participant_id: int,
) -> bool:
   

    validate_participants(
        db=db,
        from_participant_id=from_participant_id,
        to_participant_id=to_participant_id,
    )

    existing = relationship_exists(
        db=db,
        from_participant_id=from_participant_id,
        to_participant_id=to_participant_id,
    )

    if existing is not None:
        return True

    reverse = reverse_relationship_exists(
        db=db,
        from_participant_id=from_participant_id,
        to_participant_id=to_participant_id,
    )

    if reverse is not None:
        return False

    return True


def record_relationship_usage(
    db: Session,
    from_participant_id: int,
    to_participant_id: int,
) -> Relationship:
   
    relationship = relationship_exists(
        db=db,
        from_participant_id=from_participant_id,
        to_participant_id=to_participant_id,
    )

    if relationship is None:
        raise ValueError(
            "Cannot record relationship usage because the directed "
            f"relationship {from_participant_id} -> "
            f"{to_participant_id} does not exist."
        )

    now = datetime.now(timezone.utc)

    if relationship.first_used_at is None:
        relationship.first_used_at = now

    relationship.last_used_at = now
    relationship.times_used = (
        relationship.times_used or 0
    ) + 1

    db.commit()
    db.refresh(relationship)

    return relationship


def record_cycle_usage(
    db: Session,
    cycle: list[int] | tuple[int, ...],
) -> list[Relationship]:
    
    if not cycle:
        raise ValueError(
            "Cannot record usage for an empty cycle."
        )

    if len(cycle) < 2:
        raise ValueError(
            "A cycle must contain at least two participants."
        )

    # A participant may appear only once in a Hamiltonian cycle.
    if len(cycle) != len(set(cycle)):
        raise ValueError(
            "A cycle cannot contain the same participant more than once."
        )

    now = datetime.now(timezone.utc)

    relationships: list[Relationship] = []

    # ---------------------------------------------------------
    # First validate EVERY edge.
    #
    # We do this before modifying anything so that an invalid
    # cycle does not partially update relationship statistics.
    # ---------------------------------------------------------

    edges = [
        (
            cycle[index],
            cycle[(index + 1) % len(cycle)],
        )
        for index in range(len(cycle))
    ]

    for from_id, to_id in edges:

        if from_id == to_id:
            raise ValueError(
                "A participant cannot pay themselves."
            )

        relationship = relationship_exists(
            db=db,
            from_participant_id=from_id,
            to_participant_id=to_id,
        )

        if relationship is None:
            raise ValueError(
                "Cycle contains a directed edge that does not "
                f"exist: {from_id} -> {to_id}."
            )

        relationships.append(relationship)

    # ---------------------------------------------------------
    # Only update usage after the complete cycle has passed
    # validation.
    # ---------------------------------------------------------

    for relationship in relationships:

        if relationship.first_used_at is None:
            relationship.first_used_at = now

        relationship.last_used_at = now

        relationship.times_used = (
            relationship.times_used or 0
        ) + 1

    db.commit()

    for relationship in relationships:
        db.refresh(relationship)

    return relationships


def get_relationship_usage_score(
    relationship: Relationship,
    now: datetime | None = None,
) -> float:
  
    now = now or datetime.now(timezone.utc)

    times_used = relationship.times_used or 0

    score = float(times_used * 10)

    last_used = relationship.last_used_at

    if last_used is None:
        return score

    if last_used.tzinfo is None:
        last_used = last_used.replace(
            tzinfo=timezone.utc,
        )

    elapsed_days = (
        now - last_used
    ).total_seconds() / 86400

    if elapsed_days < 1:
        score += 100
    elif elapsed_days < 3:
        score += 50
    elif elapsed_days < 7:
        score += 20

    return score


def get_relationship_graph_for_account(
    db: Session,
    account_id: int,
) -> list[Relationship]:
    """
    Return only relationships whose source and destination
    participants both belong to the supplied account.

    This is the relationship set that should be passed to the
    cycle engine.
    """

    result = db.execute(
        select(Relationship)
        .join(
            Participant,
            Participant.id == Relationship.from_participant_id,
        )
        .where(
            Participant.account_id == account_id,
            Relationship.is_active.is_(True),
        )
    )

    relationships = list(
        result.scalars().all()
    )

    participant_ids = {
        participant.id
        for participant in db.execute(
            select(Participant.id).where(
                Participant.account_id == account_id,
            )
        ).scalars().all()
    }

    return [
        relationship
        for relationship in relationships
        if relationship.to_participant_id in participant_ids
    ]