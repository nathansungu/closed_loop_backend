from collections import namedtuple
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    Cycle,
    CycleParticipant,
    Participant,
    Relationship,
    Transaction,
)
from app.services.cycle_engine import MIN_PARTICIPANTS, format_cycle, generate_valid_cycle_pair
from app.services.relationship_service import record_cycle_usage
from app.services.transaction_service import (
    calculate_outgoing_transactions,
    calculate_return_transactions,
    calculate_total_circulating_amount,
)

_ParticipantAmountStub = namedtuple(
    "ParticipantAmountStub",
    ["participant_id", "initial_amount"],
)

PENDING = "pending"
OUTGOING_ACTIVE = "outgoing_active"
OUTGOING_COMPLETED = "outgoing_completed"
RETURN_ACTIVE = "return_active"
SETTLED = "settled"


TRANSACTION_COMPLETED = "completed"


def get_account(
    db: Session,
    account_id: int,
):
    """Get an account by database ID."""

    return db.get(
        Account,
        account_id,
    )


def get_cycle(
    db: Session,
    cycle_id: int,
    account_id: int | None = None,
):
    """
    Get a cycle by ID.

    When account_id is supplied, the cycle must belong
    to that account.
    """

    cycle = db.get(
        Cycle,
        cycle_id,
    )

    if cycle is None:
        return None

    if account_id is not None and cycle.account_id != account_id:
        return None

    return cycle


def get_all_cycles(
    db: Session,
    account_id: int,
):
    """Return all cycles belonging to an account."""

    result = db.execute(
        select(Cycle)
        .where(
            Cycle.account_id == account_id,
        )
        .order_by(
            Cycle.id.desc(),
        )
    )

    return result.scalars().all()


def get_cycle_participants(
    db: Session,
    cycle_id: int,
    account_id: int | None = None,
):
    """
    Get all participants registered for a cycle.
    """

    cycle = get_cycle(
        db,
        cycle_id,
        account_id,
    )

    if cycle is None:
        return []

    result = db.execute(
        select(CycleParticipant)
        .where(
            CycleParticipant.cycle_id == cycle_id,
        )
        .order_by(
            CycleParticipant.id,
        )
    )

    return result.scalars().all()


def get_cycle_participant(
    db: Session,
    cycle_id: int,
    participant_id: int,
    account_id: int | None = None,
):
    """
    Get one participant's registration inside a cycle.
    """

    cycle = get_cycle(
        db,
        cycle_id,
        account_id,
    )

    if cycle is None:
        return None

    result = db.execute(
        select(CycleParticipant).where(
            CycleParticipant.cycle_id == cycle_id,
            CycleParticipant.participant_id == participant_id,
        )
    )

    return result.scalar_one_or_none()


def get_participant_accumulation(
    db: Session,
    cycle_id: int,
    participant_id: int,
):
    """
    Calculate the participant's current accumulated value.

    Only completed transactions are included.

    Formula:

        initial_amount
        + total_received
        - total_sent
    """

    cycle_participant = get_cycle_participant(
        db=db,
        cycle_id=cycle_id,
        participant_id=participant_id,
    )

    initial_amount = (
        cycle_participant.initial_amount if cycle_participant is not None else Decimal("0.00")
    )

    received_result = db.execute(
        select(
            func.coalesce(
                func.sum(Transaction.amount),
                0,
            )
        ).where(
            Transaction.cycle_id == cycle_id,
            Transaction.to_participant_id == participant_id,
            Transaction.status == TRANSACTION_COMPLETED,
        )
    )

    sent_result = db.execute(
        select(
            func.coalesce(
                func.sum(Transaction.amount),
                0,
            )
        ).where(
            Transaction.cycle_id == cycle_id,
            Transaction.from_participant_id == participant_id,
            Transaction.status == TRANSACTION_COMPLETED,
        )
    )

    total_received = Decimal(str(received_result.scalar_one() or 0))

    total_sent = Decimal(str(sent_result.scalar_one() or 0))

    total_accumulation = initial_amount + total_received - total_sent

    return {
        "initial_amount": initial_amount,
        "total_received": total_received,
        "total_sent": total_sent,
        "total_accumulation": total_accumulation,
    }


def build_participant_detail(
    db: Session,
    participant: Participant,
    cycle_id: int | None = None,
):
    """
    Build the API representation of a participant.

    The participant name always comes directly from
    Participant.name.
    """

    initial_amount = Decimal("0.00")

    if cycle_id is not None:
        cycle_participant = get_cycle_participant(
            db=db,
            cycle_id=cycle_id,
            participant_id=participant.id,
        )

        if cycle_participant is not None:
            initial_amount = cycle_participant.initial_amount

        accumulation = get_participant_accumulation(
            db=db,
            cycle_id=cycle_id,
            participant_id=participant.id,
        )

    else:
        accumulation = {
            "initial_amount": initial_amount,
            "total_received": Decimal("0.00"),
            "total_sent": Decimal("0.00"),
            "total_accumulation": Decimal("0.00"),
        }

    return {
        "id": participant.id,
        "name": participant.name,
        "initial_amount": accumulation["initial_amount"],
        "total_received": accumulation["total_received"],
        "total_sent": accumulation["total_sent"],
        "total_accumulation": accumulation["total_accumulation"],
    }


def get_account_participant_initial_amounts(
    db: Session,
    account_id: int,
    participant_ids: list[int],
) -> dict[int, Decimal]:
    """
    Get the initial amounts for participants in an account from the database.

    Queries Participant.initial_amount directly from the participant records
    belonging to this account, ensuring configured amounts are immediately
    reflected in cycle calculations.
    """

    if not participant_ids:
        return {}

    participants = db.execute(
        select(
            Participant.id,
            Participant.initial_amount,
        )
        .where(
            Participant.account_id == account_id,
            Participant.id.in_(participant_ids),
        )
    ).all()

    amounts: dict[int, Decimal] = {}
    for pid, initial_amt in participants:
        if initial_amt is not None and initial_amt > 0:
            amounts[pid] = Decimal(str(initial_amt))

    for pid in participant_ids:
        if pid not in amounts or amounts[pid] <= 0:
            amounts[pid] = Decimal("100.00")

    return amounts


def build_generated_participant_details(
    db: Session,
    account_id: int,
    participant_ids: list[int],
    participant_metrics: dict[int, dict] | None = None,
):
    """
    Build participant details for a generated cycle with actual values
    computed from the database and simulated cycle flow.
    """

    if not participant_ids:
        return []

    result = db.execute(
        select(Participant).where(
            Participant.account_id == account_id,
            Participant.id.in_(participant_ids),
        )
    )

    participants_by_id = {participant.id: participant for participant in result.scalars().all()}

    details = []
    metrics = participant_metrics or {}

    for participant_id in participant_ids:

        participant = participants_by_id.get(participant_id)

        if participant is None:
            continue

        m = metrics.get(participant_id, {})
        details.append(
            {
                "id": participant.id,
                "name": participant.name,
                "initial_amount": m.get("initial_amount", Decimal("0.00")),
                "total_received": m.get("total_received", Decimal("0.00")),
                "total_sent": m.get("total_sent", Decimal("0.00")),
                "total_accumulation": m.get("total_accumulation", Decimal("0.00")),
            }
        )

    return details


def build_cycle_participant_details(
    db: Session,
    cycle_id: int,
):
    """
    Return all participants in a cycle with their
    transaction-derived accumulation.
    """

    result = db.execute(
        select(CycleParticipant, Participant)
        .join(
            Participant,
            Participant.id == CycleParticipant.participant_id,
        )
        .where(
            CycleParticipant.cycle_id == cycle_id,
        )
        .order_by(
            CycleParticipant.id,
        )
    )

    details = []

    for cycle_participant, participant in result.all():

        accumulation = get_participant_accumulation(
            db=db,
            cycle_id=cycle_id,
            participant_id=participant.id,
        )

        details.append(
            {
                "id": participant.id,
                "name": participant.name,
                "initial_amount": accumulation["initial_amount"],
                "total_received": accumulation["total_received"],
                "total_sent": accumulation["total_sent"],
                "total_accumulation": accumulation["total_accumulation"],
            }
        )

    return details


def create_cycle(
    db: Session,
    account_id: int,
):
    """
    Create an empty pending cycle.
    """

    account = get_account(
        db,
        account_id,
    )

    if account is None:
        raise ValueError("Account not found.")

    cycle = Cycle(
        account_id=account_id,
        status=PENDING,
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    return cycle


def add_participant_to_cycle(
    db: Session,
    account_id: int,
    cycle_id: int,
    participant_id: int,
    initial_amount: Decimal | float | int,
):
    """
    Add a participant to a pending cycle.
    """

    cycle = get_cycle(
        db,
        cycle_id,
        account_id,
    )

    if cycle is None:
        raise ValueError("Cycle not found.")

    if cycle.status != PENDING:
        raise ValueError("Participants can only be added while " "the cycle is pending.")

    participant = db.get(
        Participant,
        participant_id,
    )

    if participant is None:
        raise ValueError("Participant not found.")

    if participant.account_id != account_id:
        raise ValueError("Participant does not belong to this account.")

    existing = get_cycle_participant(
        db,
        cycle_id,
        participant_id,
        account_id,
    )

    if existing is not None:
        raise ValueError("Participant is already registered in this cycle.")

    amount = Decimal(str(initial_amount))

    if amount <= 0:
        raise ValueError("Initial amount must be greater than zero.")

    cycle_participant = CycleParticipant(
        cycle_id=cycle_id,
        participant_id=participant_id,
        initial_amount=amount,
    )

    db.add(cycle_participant)
    db.commit()
    db.refresh(cycle_participant)

    return cycle_participant


def update_cycle_participant_amount(
    db: Session,
    account_id: int,
    cycle_id: int,
    participant_id: int,
    initial_amount: Decimal | float | int,
):
    """Update a participant's initial amount while pending."""

    cycle = get_cycle(
        db,
        cycle_id,
        account_id,
    )

    if cycle is None:
        raise ValueError("Cycle not found.")

    if cycle.status != PENDING:
        raise ValueError(
            "The initial amount can no longer be changed " "because the cycle has started."
        )

    cycle_participant = get_cycle_participant(
        db,
        cycle_id,
        participant_id,
        account_id,
    )

    if cycle_participant is None:
        raise ValueError("Participant is not registered in this cycle.")

    amount = Decimal(str(initial_amount))

    if amount <= 0:
        raise ValueError("Initial amount must be greater than zero.")

    cycle_participant.initial_amount = amount

    db.commit()
    db.refresh(cycle_participant)

    return cycle_participant


def remove_participant_from_cycle(
    db: Session,
    account_id: int,
    cycle_id: int,
    participant_id: int,
):
    """Remove a participant from a pending cycle."""

    cycle = get_cycle(
        db,
        cycle_id,
        account_id,
    )

    if cycle is None:
        raise ValueError("Cycle not found.")

    if cycle.status != PENDING:
        raise ValueError("Participants cannot be removed after " "the cycle has started.")

    cycle_participant = get_cycle_participant(
        db,
        cycle_id,
        participant_id,
        account_id,
    )

    if cycle_participant is None:
        raise ValueError("Participant is not registered in this cycle.")

    db.delete(cycle_participant)
    db.commit()

    return True


def start_cycle(
    db: Session,
    account_id: int,
    cycle_id: int,
):
    """
    Lock the cycle and start the outgoing round.
    """

    cycle = get_cycle(
        db,
        cycle_id,
        account_id,
    )

    if cycle is None:
        raise ValueError("Cycle not found.")

    if cycle.status != PENDING:
        raise ValueError(
            f"Cycle cannot be started because its current " f"status is '{cycle.status}'."
        )

    participants = get_cycle_participants(
        db,
        cycle_id,
        account_id,
    )

    if len(participants) < MIN_PARTICIPANTS:
        raise ValueError(
            f"At least {MIN_PARTICIPANTS} participants are required to start a cycle (currently {len(participants)})."
        )

    cycle.status = OUTGOING_ACTIVE

    if hasattr(cycle, "started_at"):
        cycle.started_at = datetime.utcnow()

    db.commit()
    db.refresh(cycle)

    return cycle


def complete_outgoing_round(
    db: Session,
    account_id: int,
    cycle_id: int,
):
    """Mark the outgoing round as completed."""

    cycle = get_cycle(
        db,
        cycle_id,
        account_id,
    )

    if cycle is None:
        raise ValueError("Cycle not found.")

    if cycle.status != OUTGOING_ACTIVE:
        raise ValueError("The outgoing round is not currently active.")

    # Record outgoing cycle relationship usage
    try:
        mapping = get_cycle_mapping_flow(db=db, cycle_id=cycle_id)
        outgoing_cycle = [
            p["id"]
            for p in mapping.get("outgoing_cycle", [])
            if isinstance(p, dict) and "id" in p
        ]
        if len(outgoing_cycle) >= 2:
            record_cycle_usage(db=db, cycle=outgoing_cycle)
    except Exception:
        pass

    cycle.status = OUTGOING_COMPLETED

    db.commit()
    db.refresh(cycle)

    return cycle


def start_return_round(
    db: Session,
    account_id: int,
    cycle_id: int,
):
    """Start the return settlement round."""

    cycle = get_cycle(
        db,
        cycle_id,
        account_id,
    )

    if cycle is None:
        raise ValueError("Cycle not found.")

    if cycle.status != OUTGOING_COMPLETED:
        raise ValueError(
            "The outgoing round must be completed " "before starting the return round."
        )

    cycle.status = RETURN_ACTIVE

    db.commit()
    db.refresh(cycle)

    return cycle


def settle_cycle(
    db: Session,
    account_id: int,
    cycle_id: int,
):
    """Mark the cycle as settled."""

    cycle = get_cycle(
        db,
        cycle_id,
        account_id,
    )

    if cycle is None:
        raise ValueError("Cycle not found.")

    if cycle.status != RETURN_ACTIVE:
        raise ValueError("The return round must be active " "before the cycle can be settled.")

    # Record return cycle relationship usage
    try:
        mapping = get_cycle_mapping_flow(db=db, cycle_id=cycle_id)
        return_cycle = [
            p["id"]
            for p in mapping.get("return_cycle", [])
            if isinstance(p, dict) and "id" in p
        ]
        if len(return_cycle) >= 2:
            record_cycle_usage(db=db, cycle=return_cycle)
    except Exception:
        pass

    cycle.status = SETTLED

    if hasattr(cycle, "completed_at"):
        cycle.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(cycle)

    return cycle


def get_account_participants(
    db: Session,
    account_id: int,
):
    """
    Return participants belonging to an account who are eligible for
    automatic cycle generation -- i.e. active ones only.

    Inactive participants are never deleted and their relationships stay
    intact; they're just excluded from the pool that generate_valid_cycle
    / get_cycle_mapping_flow draw from, so a valid cycle can still be
    found among whoever is currently active without breaking any rule.
    """

    result = db.execute(
        select(Participant)
        .where(
            Participant.account_id == account_id,
            Participant.is_active.is_(True),
        )
        .order_by(
            Participant.id,
        )
    )

    return result.scalars().all()


def get_account_participant_ids(
    db: Session,
    account_id: int,
):
    """Return participant IDs belonging to an account."""

    return [
        participant.id
        for participant in get_account_participants(
            db,
            account_id,
        )
    ]


def get_account_relationships(
    db: Session,
    account_id: int,
):
    """
    Get relationships where both participants belong
    to the same account.
    """

    participants = get_account_participants(
        db,
        account_id,
    )

    participant_ids = {participant.id for participant in participants}

    if not participant_ids:
        return []

    result = db.execute(
        select(Relationship)
        .join(
            Participant,
            Relationship.from_participant_id == Participant.id,
        )
        .where(
            Participant.account_id == account_id,
            Relationship.is_active.is_(True),
        )
    )

    relationships = result.scalars().all()

    return [
        relationship
        for relationship in relationships
        if relationship.to_participant_id in participant_ids
    ]


def generate_valid_cycle(
    db: Session,
    account_id: int,
    start_participant_id=None,
):
    """
    Generate a valid outgoing + return cycle and compute actual money movements
    and participant metrics from the database and cycle transaction flow.

    Does not move money, create persistent database transactions, update balances,
    or start the cycle -- that happens later via start_cycle / transaction_service.
    """

    account = get_account(db, account_id)
    if account is None:
        raise ValueError("Account not found.")

    participant_ids = get_account_participant_ids(db, account_id)
    if not participant_ids:
        raise ValueError("No participants found for this account.")

    relationships = get_account_relationships(db, account_id)

    generated = generate_valid_cycle_pair(
        participant_ids=participant_ids,
        relationships=relationships,
        start_participant_id=start_participant_id,
    )

    outgoing_cycle = generated["outgoing_cycle"]
    return_cycle = generated["return_cycle"]

    # -----------------------------------------------------
    # Retrieve initial amounts computed from database history
    # -----------------------------------------------------
    initial_amounts = get_account_participant_initial_amounts(
        db=db,
        account_id=account_id,
        participant_ids=participant_ids,
    )

    # -----------------------------------------------------
    # Prepare participant stubs for transaction calculation
    # -----------------------------------------------------
    stubs = [
        _ParticipantAmountStub(
            participant_id=pid,
            initial_amount=initial_amounts.get(pid, Decimal("100.00")),
        )
        for pid in participant_ids
    ]

    # -----------------------------------------------------
    # Calculate actual cycle flow transactions
    # -----------------------------------------------------
    outgoing_transactions = calculate_outgoing_transactions(
        cycle_participants=stubs,
        outgoing_cycle=outgoing_cycle,
    )

    return_transactions = calculate_return_transactions(
        cycle_participants=stubs,
        outgoing_cycle=outgoing_cycle,
        return_cycle=return_cycle,
        outgoing_transactions=outgoing_transactions,
    )

    total_circulating_amount = calculate_total_circulating_amount(outgoing_transactions)

    # -----------------------------------------------------
    # Compute participant flow metrics (received, sent, accumulation)
    # -----------------------------------------------------
    tot_received: dict[int, Decimal] = {pid: Decimal("0.00") for pid in participant_ids}
    tot_sent: dict[int, Decimal] = {pid: Decimal("0.00") for pid in participant_ids}

    for tx in outgoing_transactions + return_transactions:
        tot_sent[tx["from_participant_id"]] += Decimal(str(tx["amount"]))
        tot_received[tx["to_participant_id"]] += Decimal(str(tx["amount"]))

    participant_metrics = {}
    for pid in participant_ids:
        initial_amt = initial_amounts.get(pid, Decimal("100.00"))
        received = tot_received[pid]
        sent = tot_sent[pid]
        total_accumulation = initial_amt + received - sent
        participant_metrics[pid] = {
            "initial_amount": initial_amt,
            "total_received": received,
            "total_sent": sent,
            "total_accumulation": total_accumulation,
        }

    participant_details = build_generated_participant_details(
        db=db,
        account_id=account_id,
        participant_ids=participant_ids,
        participant_metrics=participant_metrics,
    )
    details_by_id = {item["id"]: item for item in participant_details}

    return {
        "account_id": account_id,
        "participant_ids": participant_ids,
        "total_circulating_amount": total_circulating_amount,
        "participants": participant_details,
        "outgoing_cycle": [details_by_id[pid] for pid in outgoing_cycle],
        "return_cycle": [details_by_id[pid] for pid in return_cycle],
        "outgoing_transactions": outgoing_transactions,
        "return_transactions": return_transactions,
    }


def create_generated_cycle(
    db: Session,
    account_id: int,
    start_participant_id=None,
):
    """
    Generate and persist a cycle structure.

    Initial amounts are zero because this function creates
    the cycle before the user assigns participant amounts.
    """

    generated = generate_valid_cycle(
        db=db,
        account_id=account_id,
        start_participant_id=start_participant_id,
    )

    cycle = Cycle(
        account_id=account_id,
        status=PENDING,
    )

    db.add(cycle)

    try:

        db.flush()

        for participant_id in generated["participant_ids"]:

            cycle_participant = CycleParticipant(
                cycle_id=cycle.id,
                participant_id=participant_id,
                initial_amount=Decimal("0.00"),
            )

            db.add(cycle_participant)

        db.commit()
        db.refresh(cycle)

    except Exception:
        db.rollback()
        raise

    return {
        "cycle": cycle,
        "outgoing_cycle": generated["outgoing_cycle"],
        "return_cycle": generated["return_cycle"],
        "participant_ids": generated["participant_ids"],
    }


def get_cycle_mapping_flow(
    db: Session,
    cycle_id: int,
) -> dict:
    """
    Get the mapping relationship, outgoing route, return route,
    and step-by-step transaction flow for an existing cycle.
    """
    cycle = get_cycle(db=db, cycle_id=cycle_id)
    if not cycle:
        raise ValueError("Cycle not found.")

    cycle_participants = get_cycle_participants(db=db, cycle_id=cycle_id)
    participant_ids = [cp.participant_id for cp in cycle_participants]

    if not participant_ids:
        account_participants = get_account_participants(db=db, account_id=cycle.account_id)
        participant_ids = [p.id for p in account_participants]
        initial_amounts = get_account_participant_initial_amounts(
            db=db, account_id=cycle.account_id, participant_ids=participant_ids
        )
    else:
        initial_amounts = {cp.participant_id: cp.initial_amount for cp in cycle_participants}

    if len(participant_ids) < MIN_PARTICIPANTS:
        metrics = {
            pid: {
                "initial_amount": initial_amounts.get(pid, Decimal("100.00")),
                "total_received": Decimal("0.00"),
                "total_sent": Decimal("0.00"),
                "total_accumulation": initial_amounts.get(pid, Decimal("100.00")),
            }
            for pid in participant_ids
        }
        participants_data = build_generated_participant_details(
            db=db,
            account_id=cycle.account_id,
            participant_ids=participant_ids,
            participant_metrics=metrics,
        )
        return {
            "account_id": cycle.account_id,
            "participant_ids": participant_ids,
            "total_circulating_amount": sum(initial_amounts.values(), Decimal("0.00")),
            "participants": participants_data,
            "outgoing_cycle": participants_data,
            "return_cycle": participants_data,
            "outgoing_transactions": [],
            "return_transactions": [],
        }

    relationships = get_account_relationships(db=db, account_id=cycle.account_id)
    if not relationships:
        metrics = {
            pid: {
                "initial_amount": initial_amounts.get(pid, Decimal("100.00")),
                "total_received": Decimal("0.00"),
                "total_sent": Decimal("0.00"),
                "total_accumulation": initial_amounts.get(pid, Decimal("100.00")),
            }
            for pid in participant_ids
        }
        participants_data = build_generated_participant_details(
            db=db,
            account_id=cycle.account_id,
            participant_ids=participant_ids,
            participant_metrics=metrics,
        )
        return {
            "account_id": cycle.account_id,
            "participant_ids": participant_ids,
            "total_circulating_amount": sum(initial_amounts.values(), Decimal("0.00")),
            "participants": participants_data,
            "outgoing_cycle": [],
            "return_cycle": [],
            "outgoing_transactions": [],
            "return_transactions": [],
        }

    try:
        generated_cycles = generate_valid_cycle_pair(
            participant_ids=participant_ids,
            relationships=relationships,
        )
    except ValueError:
        metrics = {
            pid: {
                "initial_amount": initial_amounts.get(pid, Decimal("100.00")),
                "total_received": Decimal("0.00"),
                "total_sent": Decimal("0.00"),
                "total_accumulation": initial_amounts.get(pid, Decimal("100.00")),
            }
            for pid in participant_ids
        }
        participants_data = build_generated_participant_details(
            db=db,
            account_id=cycle.account_id,
            participant_ids=participant_ids,
            participant_metrics=metrics,
        )
        return {
            "account_id": cycle.account_id,
            "participant_ids": participant_ids,
            "total_circulating_amount": sum(initial_amounts.values(), Decimal("0.00")),
            "participants": participants_data,
            "outgoing_cycle": [],
            "return_cycle": [],
            "outgoing_transactions": [],
            "return_transactions": [],
        }

    outgoing_cycle_ids = generated_cycles["outgoing_cycle"]
    return_cycle_ids = generated_cycles["return_cycle"]

    stubs = [
        _ParticipantAmountStub(
            participant_id=pid,
            initial_amount=initial_amounts.get(pid, Decimal("100.00")),
        )
        for pid in participant_ids
    ]

    outgoing_transactions = calculate_outgoing_transactions(
        cycle_participants=stubs,
        outgoing_cycle=outgoing_cycle_ids,
    )
    return_transactions = calculate_return_transactions(
        cycle_participants=stubs,
        outgoing_cycle=outgoing_cycle_ids,
        return_cycle=return_cycle_ids,
        outgoing_transactions=outgoing_transactions,
    )
    total_circulating_amount = calculate_total_circulating_amount(outgoing_transactions)

    participant_metrics: dict[int, dict] = {}
    for pid in participant_ids:
        init_amt = initial_amounts.get(pid, Decimal("100.00"))
        tot_recv = Decimal("0.00")
        tot_sent = Decimal("0.00")
        for tx in outgoing_transactions + return_transactions:
            if tx["to_participant_id"] == pid:
                tot_recv += tx["amount"]
            if tx["from_participant_id"] == pid:
                tot_sent += tx["amount"]
        tot_accum = init_amt + tot_recv - tot_sent
        participant_metrics[pid] = {
            "initial_amount": init_amt,
            "total_received": tot_recv,
            "total_sent": tot_sent,
            "total_accumulation": tot_accum,
        }

    participants_details = build_generated_participant_details(
        db=db,
        account_id=cycle.account_id,
        participant_ids=participant_ids,
        participant_metrics=participant_metrics,
    )
    outgoing_cycle_details = build_generated_participant_details(
        db=db,
        account_id=cycle.account_id,
        participant_ids=outgoing_cycle_ids,
        participant_metrics=participant_metrics,
    )
    return_cycle_details = build_generated_participant_details(
        db=db,
        account_id=cycle.account_id,
        participant_ids=return_cycle_ids,
        participant_metrics=participant_metrics,
    )

    return {
        "account_id": cycle.account_id,
        "participant_ids": participant_ids,
        "total_circulating_amount": total_circulating_amount,
        "participants": participants_details,
        "outgoing_cycle": outgoing_cycle_details,
        "return_cycle": return_cycle_details,
        "outgoing_transactions": outgoing_transactions,
        "return_transactions": return_transactions,
    }


def display_cycle(
    label,
    cycle,
):
    """Print a cycle in readable form."""

    print(f"\n{label}:")

    if cycle:
        print(format_cycle(cycle))
    else:
        print("No valid cycle found.")

