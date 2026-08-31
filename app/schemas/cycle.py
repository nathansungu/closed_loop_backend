from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CycleCreate(BaseModel):
    account_id: int


class CycleParticipantCreate(BaseModel):
    participant_id: int
    initial_amount: Decimal = Field(
        ...,
        gt=0,
    )


class CycleParticipantResponse(BaseModel):
    id: int
    cycle_id: int
    participant_id: int
    initial_amount: Decimal

    model_config = ConfigDict(
        from_attributes=True,
    )


class CycleParticipantDetail(BaseModel):
    """
    Participant information used when displaying a cycle.

    total_accumulation is calculated from:

        initial_amount
        + completed money received
        - completed money sent
    """

    id: int
    name: str
    initial_amount: Decimal
    total_received: Decimal
    total_sent: Decimal
    total_accumulation: Decimal


class GeneratedTransaction(BaseModel):
    round: str
    from_participant_id: int
    to_participant_id: int
    amount: Decimal


class GeneratedCycleParticipant(BaseModel):
    """
    Participant representation returned by the cycle generator.
    """

    id: int
    name: str
    initial_amount: Decimal
    total_received: Decimal
    total_sent: Decimal
    total_accumulation: Decimal


class GeneratedCycleResponse(BaseModel):
    account_id: int
    participant_ids: list[int]
    total_circulating_amount: Decimal = Decimal("0.00")

    participants: list[GeneratedCycleParticipant]

    outgoing_cycle: list[GeneratedCycleParticipant]
    return_cycle: list[GeneratedCycleParticipant]

    outgoing_transactions: list[GeneratedTransaction] = []
    return_transactions: list[GeneratedTransaction] = []


class CycleResponse(BaseModel):
    id: int
    uuid: str
    account_id: int
    status: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True,
    )
