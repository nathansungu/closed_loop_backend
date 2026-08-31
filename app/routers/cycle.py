from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.schemas.cycle import (
    CycleCreate,
    CycleParticipantCreate,
    CycleParticipantResponse,
    CycleResponse,
    GeneratedCycleResponse,
)

from app.services.cycle_service import (
    add_participant_to_cycle,
    complete_outgoing_round,
    create_cycle,
    get_all_cycles,
    get_cycle,
    get_cycle_participant,
    get_cycle_participants,
    get_cycle_mapping_flow,
    generate_valid_cycle,
    remove_participant_from_cycle,
    settle_cycle,
    start_cycle,
    start_return_round,
    update_cycle_participant_amount,
)

router = APIRouter(
    prefix="/cycles",
    tags=["Cycles"],
)


@router.post(
    "/",
    response_model=CycleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: CycleCreate,
    db: Session = Depends(get_db),
):
    """Create a new pending cycle."""

    try:

        return create_cycle(
            db=db,
            account_id=data.account_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/account/{account_id}",
    response_model=list[CycleResponse],
)
def list_account_cycles(
    account_id: int,
    db: Session = Depends(get_db),
):
    """Return all cycles belonging to an account."""

    return get_all_cycles(
        db=db,
        account_id=account_id,
    )


@router.get(
    "/{cycle_id}",
    response_model=CycleResponse,
)
def get(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    """Get a cycle by ID."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    return cycle


@router.post(
    "/account/{account_id}/generate",
    response_model=GeneratedCycleResponse,
)
def generate(
    account_id: int,
    start_participant_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Generate a valid outgoing and return cycle.

    This computes actual participant initial amounts from the database,
    simulates the full cycle transaction flow, and returns computed
    values without moving real money or persisting a cycle.
    """

    try:

        return generate_valid_cycle(
            db=db,
            account_id=account_id,
            start_participant_id=start_participant_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/{cycle_id}/mapping",
    response_model=GeneratedCycleResponse,
)
def get_mapping(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    """
    Get the mapping relationship routes, outgoing flow, return flow,
    and step-by-step transaction ledger for any active or pending cycle.
    """
    try:
        return get_cycle_mapping_flow(db=db, cycle_id=cycle_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/{cycle_id}/participants",
    response_model=list[CycleParticipantResponse],
)
def list_participants(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    """Return all participants registered in a cycle."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    return get_cycle_participants(
        db=db,
        cycle_id=cycle_id,
    )


@router.post(
    "/{cycle_id}/participants",
    response_model=CycleParticipantResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_participant(
    cycle_id: int,
    data: CycleParticipantCreate,
    db: Session = Depends(get_db),
):
    """Add a participant to a pending cycle."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    try:

        return add_participant_to_cycle(
            db=db,
            account_id=cycle.account_id,
            cycle_id=cycle_id,
            participant_id=data.participant_id,
            initial_amount=data.initial_amount,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/{cycle_id}/participants/{participant_id}",
    response_model=CycleParticipantResponse,
)
def get_participant(
    cycle_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
):
    """Get one participant's registration inside a cycle."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    cycle_participant = get_cycle_participant(
        db=db,
        cycle_id=cycle_id,
        participant_id=participant_id,
        account_id=cycle.account_id,
    )

    if cycle_participant is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=("Participant is not registered " "in this cycle."),
        )

    return cycle_participant


@router.put(
    "/{cycle_id}/participants/{participant_id}",
    response_model=CycleParticipantResponse,
)
def update_participant_amount(
    cycle_id: int,
    participant_id: int,
    data: CycleParticipantCreate,
    db: Session = Depends(get_db),
):
    """Update a participant's initial amount."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    try:

        return update_cycle_participant_amount(
            db=db,
            account_id=cycle.account_id,
            cycle_id=cycle_id,
            participant_id=participant_id,
            initial_amount=data.initial_amount,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.delete(
    "/{cycle_id}/participants/{participant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_participant(
    cycle_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
):
    """Remove a participant from a pending cycle."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    try:

        remove_participant_from_cycle(
            db=db,
            account_id=cycle.account_id,
            cycle_id=cycle_id,
            participant_id=participant_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return None


@router.post(
    "/{cycle_id}/start",
    response_model=CycleResponse,
)
def start(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    """Start the outgoing round."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    try:

        return start_cycle(
            db=db,
            account_id=cycle.account_id,
            cycle_id=cycle_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/{cycle_id}/complete-outgoing",
    response_model=CycleResponse,
)
def complete_outgoing(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    """Mark the outgoing round as completed."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    try:

        return complete_outgoing_round(
            db=db,
            account_id=cycle.account_id,
            cycle_id=cycle_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/{cycle_id}/start-return",
    response_model=CycleResponse,
)
def start_return(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    """Start the return settlement round."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    try:

        return start_return_round(
            db=db,
            account_id=cycle.account_id,
            cycle_id=cycle_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post(
    "/{cycle_id}/settle",
    response_model=CycleResponse,
)
def settle(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    """Mark the cycle as settled."""

    cycle = get_cycle(
        db=db,
        cycle_id=cycle_id,
    )

    if cycle is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found.",
        )

    try:

        return settle_cycle(
            db=db,
            account_id=cycle.account_id,
            cycle_id=cycle_id,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
