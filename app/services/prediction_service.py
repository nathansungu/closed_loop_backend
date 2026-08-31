from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.models import Relationship

from app.services.cycle_engine import (
    build_graph,
    generate_outgoing_cycle,
    generate_return_cycle,
)


@dataclass
class PredictedCycle:
    period: int
    date: datetime
    outgoing_cycle: list[int]
    return_cycle: list[int]


def _relationship_key(
    from_id: int,
    to_id: int,
) -> tuple[int, int]:
    return from_id, to_id


def _clone_relationships_for_prediction(
    relationships: list[Relationship],
) -> list[Relationship]:
    """
    Create lightweight copies of relationships.

    Prediction must NEVER modify SQLAlchemy model instances
    attached to the real database session.
    """

    cloned: list[Relationship] = []

    for relationship in relationships:

        clone = Relationship(
            id=relationship.id,
            from_participant_id=relationship.from_participant_id,
            to_participant_id=relationship.to_participant_id,
            first_used_at=relationship.first_used_at,
            last_used_at=relationship.last_used_at,
            times_used=relationship.times_used or 0,
        )

        cloned.append(clone)

    return cloned


def _build_prediction_graph(
    relationships: list[Relationship],
):
    """
    Build a NetworkX graph from the simulated relationships.

    The prediction graph is rebuilt after every predicted period
    because relationship usage changes during simulation.
    """

    return build_graph(relationships)


def _record_predicted_usage(
    relationships: list[Relationship],
    cycle: list[int],
    predicted_date: datetime,
) -> None:
    """
    Simulate relationship usage in memory.

    This function modifies only cloned relationship objects.
    Nothing is committed to the database.
    """

    if not cycle:
        return

    relationship_map = {
        _relationship_key(
            relationship.from_participant_id,
            relationship.to_participant_id,
        ): relationship
        for relationship in relationships
    }

    for index in range(len(cycle)):

        from_id = cycle[index]
        to_id = cycle[(index + 1) % len(cycle)]

        relationship = relationship_map.get(
            _relationship_key(
                from_id,
                to_id,
            )
        )

        if not relationship:
            continue

        if relationship.first_used_at is None:
            relationship.first_used_at = predicted_date

        relationship.last_used_at = predicted_date

        relationship.times_used = (relationship.times_used or 0) + 1


def _validate_prediction(
    participant_ids: list[int],
    outgoing_cycle: list[int],
    return_cycle: list[int],
    graph,
) -> bool:
    """
    Validate the basic prediction rules.

    The detailed cycle validation remains inside
    cycle_engine.py. This function protects the
    prediction service from accepting an invalid pair.
    """

    if not outgoing_cycle:
        return False

    if not return_cycle:
        return False

    if len(outgoing_cycle) != len(participant_ids):
        return False

    if len(return_cycle) != len(participant_ids):
        return False

    # The person who starts the outgoing round must also
    # start the return round.
    if outgoing_cycle[0] != return_cycle[0]:
        return False

    return True


def predict_cycles(
    participant_ids: list[int],
    relationships: list[Relationship],
    periods: int = 365,
    start_date: Optional[datetime] = None,
) -> list[PredictedCycle]:
    """
    Predict future outgoing and return cycles.

    Parameters
    ----------
    participant_ids:
        All participants participating in the system.

    relationships:
        Current relationship records from the database.

    periods:
        Number of future periods to predict.

        Examples:
            7   -> next 7 days
            30  -> next 30 days
            365 -> next year

    start_date:
        Date from which prediction should begin.

        Defaults to tomorrow.

    Returns
    -------
    list[PredictedCycle]

    IMPORTANT
    ---------
    This function does NOT modify the database.

    Relationship usage is simulated using cloned
    relationship objects in memory.
    """

    # -----------------------------------------------------
    # Basic validation
    # -----------------------------------------------------

    if not participant_ids or len(participant_ids) < 5 or not relationships or periods <= 0:
        return []

    # -----------------------------------------------------
    # Default prediction start date
    # -----------------------------------------------------

    if start_date is None:
        start_date = datetime.utcnow() + timedelta(days=1)

    # -----------------------------------------------------
    # Clone relationships.
    #
    # These are the objects that will be modified during
    # prediction. The actual database objects remain untouched.
    # -----------------------------------------------------

    simulated_relationships = _clone_relationships_for_prediction(relationships or [])

    predictions: list[PredictedCycle] = []

    # -----------------------------------------------------
    # Keep track of the previous outgoing starter.
    #
    # This encourages the prediction engine to rotate
    # starters instead of repeatedly selecting the same
    # participant.
    # -----------------------------------------------------

    previous_start: Optional[int] = None
    from app.services.cycle_engine import generate_valid_cycle_pair, choose_starting_participant

    for period in range(1, periods + 1):
        prediction_date = start_date + timedelta(days=period - 1)

        # Rotate starter candidate
        start_id = choose_starting_participant(participant_ids, previous_start=previous_start)

        try:
            pair = generate_valid_cycle_pair(
                participant_ids=participant_ids,
                relationships=simulated_relationships,
                start_participant_id=start_id,
            )
        except Exception:
            # If constrained, retry with another starter
            try:
                pair = generate_valid_cycle_pair(
                    participant_ids=participant_ids,
                    relationships=simulated_relationships,
                )
            except Exception:
                continue

        outgoing_cycle = pair.get("outgoing_cycle", [])
        return_cycle = pair.get("return_cycle", [])

        if not outgoing_cycle or not return_cycle:
            continue

        predictions.append(
            PredictedCycle(
                period=period,
                date=prediction_date,
                outgoing_cycle=outgoing_cycle,
                return_cycle=return_cycle,
            )
        )

        previous_start = outgoing_cycle[0]

        # Record predicted usage on simulated relationships
        _record_predicted_usage(
            simulated_relationships,
            outgoing_cycle,
            prediction_date,
        )

        _record_predicted_usage(
            simulated_relationships,
            return_cycle,
            prediction_date,
        )

    return predictions


def predict_cycles_for_year(
    participant_ids: list[int],
    relationships: list[Relationship],
    start_date: Optional[datetime] = None,
) -> list[PredictedCycle]:
    """
    Convenience method for a one-year prediction.
    """

    return predict_cycles(
        participant_ids=participant_ids,
        relationships=relationships,
        periods=365,
        start_date=start_date,
    )


def predict_cycles_for_month(
    participant_ids: list[int],
    relationships: list[Relationship],
    start_date: Optional[datetime] = None,
) -> list[PredictedCycle]:
    """
    Convenience method for a 30-day prediction.
    """

    return predict_cycles(
        participant_ids=participant_ids,
        relationships=relationships,
        periods=30,
        start_date=start_date,
    )


def predict_cycles_for_week(
    participant_ids: list[int],
    relationships: list[Relationship],
    start_date: Optional[datetime] = None,
) -> list[PredictedCycle]:
    """
    Convenience method for a 7-day prediction.
    """

    return predict_cycles(
        participant_ids=participant_ids,
        relationships=relationships,
        periods=7,
        start_date=start_date,
    )
