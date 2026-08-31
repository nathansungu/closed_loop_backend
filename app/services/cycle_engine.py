from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Sequence


# ============================================================
# CONFIGURATION
# ============================================================

# The algorithm requires at least five participants.
#
# With fewer than five participants, it is generally impossible
# to construct two distinct directed Hamiltonian cycles while
# also preserving the no-reverse-edge rule.
MIN_PARTICIPANTS = 5

DEFAULT_MAX_SEARCH_STEPS = 50_000
DEFAULT_MAX_CANDIDATES = 25

TOP_K_FOR_RANDOM_CHOICE = 3


# ============================================================
# GRAPH CONSTRUCTION
# ============================================================

def build_graph(relationships: Iterable) -> dict[int, set[int]]:
    """
    Build a directed adjacency graph from database relationships.

    Every relationship represents exactly one allowed direction:

        A -> B

    No reverse or synthetic relationship is ever created.
    """

    adjacency: dict[int, set[int]] = defaultdict(set)

    for relationship in relationships:
        from_id = relationship.from_participant_id
        to_id = relationship.to_participant_id

        if from_id == to_id:
            continue

        adjacency[from_id].add(to_id)

    return dict(adjacency)


# ============================================================
# CYCLE UTILITIES
# ============================================================

def cycle_to_edges(
    cycle: Sequence[int],
) -> set[tuple[int, int]]:
    """
    Convert a circular participant sequence into directed edges.

    Example:

        [1, 2, 3]

    becomes:

        {
            (1, 2),
            (2, 3),
            (3, 1),
        }
    """

    if not cycle:
        return set()

    return {
        (
            cycle[index],
            cycle[(index + 1) % len(cycle)],
        )
        for index in range(len(cycle))
    }


def normalize_cycle(
    cycle: Sequence[int],
) -> list[int]:
    """
    Normalize a circular cycle by rotating it so the smallest
    participant ID appears first.

    Direction is preserved.

    Example:

        [3, 4, 1, 2]

    becomes:

        [1, 2, 3, 4]
    """

    if not cycle:
        return []

    values = list(cycle)

    minimum_index = values.index(min(values))

    return (
        values[minimum_index:]
        + values[:minimum_index]
    )


def rotate_cycle(
    cycle: Sequence[int],
    start: int,
) -> list[int] | None:
    """
    Rotate a cycle so that `start` becomes the first participant.
    """

    if not cycle or start not in cycle:
        return None

    values = list(cycle)
    index = values.index(start)

    return values[index:] + values[:index]


def format_cycle(
    cycle: Sequence[int],
) -> str:
    """
    Format a cycle for display.
    """

    if not cycle:
        return ""

    return (
        " → ".join(map(str, cycle))
        + f" → {cycle[0]}"
    )


def choose_starting_participant(
    participant_ids: Sequence[int],
    previous_start: int | None = None,
    rng=None,
) -> int | None:
    """
    Select a starting participant.

    If possible, avoid using the previous starting participant.
    """

    rng = rng or random

    candidates = list(participant_ids)

    if not candidates:
        return None

    if (
        previous_start is not None
        and len(candidates) > 1
    ):
        candidates = [
            participant_id
            for participant_id in candidates
            if participant_id != previous_start
        ]

    return rng.choice(candidates)


# ============================================================
# HAMILTONIAN CYCLE SEARCH
# ============================================================

def search_hamiltonian_cycles(
    adjacency: dict[int, set[int]],
    participant_ids: Sequence[int],
    start_participant: int,
    forbidden_edges: frozenset[tuple[int, int]] = frozenset(),
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    max_steps: int = DEFAULT_MAX_SEARCH_STEPS,
    rng=None,
) -> list[list[int]]:
    """
    Search for directed Hamiltonian cycles.

    Requirements:

    1. Every participant must appear exactly once.
    2. Every movement must follow an existing directed relationship.
    3. The final participant must connect back to the start.
    4. Forbidden edges are never used.
    5. Search is bounded by max_steps.
    6. At most max_candidates are returned.

    The cycle returned does NOT repeat the starting participant
    at the end.

    Example:

        [1, 2, 3, 4, 5]

    represents:

        1 → 2 → 3 → 4 → 5 → 1
    """

    rng = rng or random

    participant_ids = list(dict.fromkeys(participant_ids))
    participant_set = set(participant_ids)

    if start_participant not in participant_set:
        return []

    if len(participant_set) < 2:
        return []

    if max_candidates <= 0 or max_steps <= 0:
        return []

    results: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()

    steps = 0

    def dfs(
        path: list[int],
        visited: set[int],
    ) -> None:
        nonlocal steps

        if steps >= max_steps:
            return

        if len(results) >= max_candidates:
            return

        steps += 1

        current = path[-1]

        # ----------------------------------------------------
        # All participants have been visited.
        # We now need the closing edge:
        #
        # current -> start
        # ----------------------------------------------------
        if len(path) == len(participant_set):
            closing_edge = (
                current,
                start_participant,
            )

            if (
                start_participant
                in adjacency.get(current, set())
                and closing_edge not in forbidden_edges
            ):
                key = tuple(path)

                if key not in seen:
                    seen.add(key)
                    results.append(list(path))

            return

        neighbors = [
            neighbor
            for neighbor in adjacency.get(current, set())
            if neighbor in participant_set
            and neighbor not in visited
            and (
                current,
                neighbor,
            ) not in forbidden_edges
        ]

        rng.shuffle(neighbors)

        for neighbor in neighbors:
            if steps >= max_steps:
                return

            if len(results) >= max_candidates:
                return

            path.append(neighbor)
            visited.add(neighbor)

            dfs(
                path,
                visited,
            )

            visited.remove(neighbor)
            path.pop()

    dfs(
        [start_participant],
        {start_participant},
    )

    return results


# ============================================================
# FULL CYCLE DISCOVERY
# ============================================================

def find_all_full_cycles(
    graph: dict[int, set[int]],
    participant_ids: Sequence[int],
    rng=None,
) -> list[list[int]]:
    """
    Find Hamiltonian cycles from every possible starting point.

    This is primarily a diagnostic/debugging helper.

    Generation should normally use generate_valid_cycle_pair().
    """

    rng = rng or random

    participant_ids = list(participant_ids)

    results: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()

    for start in participant_ids:
        cycles = search_hamiltonian_cycles(
            adjacency=graph,
            participant_ids=participant_ids,
            start_participant=start,
            rng=rng,
        )

        for cycle in cycles:
            normalized = tuple(
                normalize_cycle(cycle)
            )

            if normalized in seen:
                continue

            seen.add(normalized)
            results.append(cycle)

    return results


# ============================================================
# CYCLE COMPARISON
# ============================================================

def is_same_cycle(
    cycle1: Sequence[int],
    cycle2: Sequence[int],
) -> bool:
    """
    Determine whether two cycles represent the same directed
    circular route.

    Rotation does not matter.

    Direction DOES matter.

    Example:

        1 → 2 → 3 → 4

    and

        3 → 4 → 1 → 2

    are the same cycle.
    """

    if not cycle1 or not cycle2:
        return False

    if len(cycle1) != len(cycle2):
        return False

    return (
        normalize_cycle(cycle1)
        == normalize_cycle(cycle2)
    )


def is_reverse_cycle(
    cycle1: Sequence[int],
    cycle2: Sequence[int],
) -> bool:
    """
    Determine whether cycle2 is the exact reverse of cycle1.
    """

    if not cycle1 or not cycle2:
        return False

    if len(cycle1) != len(cycle2):
        return False

    reversed_cycle = list(
        reversed(cycle1)
    )

    return (
        normalize_cycle(reversed_cycle)
        == normalize_cycle(cycle2)
    )


def has_reverse_edge_conflict(
    outgoing_cycle: Sequence[int],
    return_cycle: Sequence[int],
) -> bool:
    """
    Determine whether the return cycle contains any edge that
    reverses an edge used by the outgoing cycle.

    If outgoing contains:

        A -> B

    return may NOT contain:

        B -> A

    This is a core Closed Loop rule.
    """

    outgoing_edges = cycle_to_edges(
        outgoing_cycle
    )

    return any(
        (
            to_id,
            from_id,
        ) in cycle_to_edges(return_cycle)
        for from_id, to_id in outgoing_edges
    )


def has_shared_directed_edge(
    outgoing_cycle: Sequence[int],
    return_cycle: Sequence[int],
) -> bool:
    """
    Check whether both cycles use the exact same directed edge.

    This is NOT prohibited by the basic algorithm, but keeping
    this helper separate makes the rule explicit.

    Example:

        Outgoing: 1 -> 2
        Return:   1 -> 2

    is a shared directed edge.
    """

    return bool(
        cycle_to_edges(outgoing_cycle)
        & cycle_to_edges(return_cycle)
    )


# ============================================================
# CYCLE VALIDATION
# ============================================================

def validate_cycle(
    graph: dict[int, set[int]],
    cycle: Sequence[int],
    participant_ids: Sequence[int],
) -> bool:
    """
    Validate a complete directed Hamiltonian cycle.

    Rules:

    1. Every participant is included.
    2. Every participant appears exactly once.
    3. No self-loop exists.
    4. Every edge exists in the directed relationship graph.
    5. The final participant connects back to the first.
    """

    participant_ids = list(
        dict.fromkeys(participant_ids)
    )

    participant_set = set(
        participant_ids
    )

    if len(participant_set) < 2:
        return False

    if not cycle:
        return False

    if len(cycle) != len(participant_set):
        return False

    if set(cycle) != participant_set:
        return False

    if len(cycle) != len(set(cycle)):
        return False

    for from_id, to_id in cycle_to_edges(cycle):

        if from_id == to_id:
            return False

        if to_id not in graph.get(
            from_id,
            set(),
        ):
            return False

    return True


def validate_two_cycles(
    graph: dict[int, set[int]],
    outgoing_cycle: Sequence[int],
    return_cycle: Sequence[int],
    participant_ids: Sequence[int],
) -> bool:
    """
    Strict validation of the outgoing + return cycle pair.

    Rules:

    1. Both cycles must contain every participant.
    2. Both cycles must be directed.
    3. Both cycles must use existing relationships.
    4. Both cycles must start at the same participant.
    5. The cycles cannot be identical.
    6. The return cycle cannot be the reverse of the outgoing cycle.
    7. The return cycle cannot reverse ANY outgoing edge.

    Rule 7 is stronger than simply checking is_reverse_cycle().
    """

    if not outgoing_cycle or not return_cycle:
        return False

    if not validate_cycle(
        graph,
        outgoing_cycle,
        participant_ids,
    ):
        return False

    if not validate_cycle(
        graph,
        return_cycle,
        participant_ids,
    ):
        return False

    if outgoing_cycle[0] != return_cycle[0]:
        return False

    if is_same_cycle(
        outgoing_cycle,
        return_cycle,
    ):
        return False

    if is_reverse_cycle(
        outgoing_cycle,
        return_cycle,
    ):
        return False

    if has_reverse_edge_conflict(
        outgoing_cycle,
        return_cycle,
    ):
        return False

    return True


# ============================================================
# RELATIONSHIP USAGE SCORING
# ============================================================

def score_cycle(
    cycle: Sequence[int],
    relationships: Iterable | None,
) -> float:
    """
    Lower score is better.

    Penalizes:

    - frequently used relationships
    - relationships used very recently

    This does NOT change validity.

    It only determines which valid candidate is preferred.
    """

    if not relationships:
        return 0.0

    relationship_map = {
        (
            relationship.from_participant_id,
            relationship.to_participant_id,
        ): relationship
        for relationship in relationships
    }

    score = 0.0

    now = datetime.now(
        timezone.utc
    )

    for from_id, to_id in cycle_to_edges(
        cycle
    ):
        relationship = relationship_map.get(
            (from_id, to_id)
        )

        if relationship is None:
            continue

        times_used = getattr(
            relationship,
            "times_used",
            0,
        ) or 0

        score += times_used * 10

        last_used = getattr(
            relationship,
            "last_used_at",
            None,
        )

        if last_used is None:
            continue

        if last_used.tzinfo is None:
            last_used = last_used.replace(
                tzinfo=timezone.utc
            )

        days_since_use = (
            now - last_used
        ).total_seconds() / 86400

        if days_since_use < 1:
            score += 100

        elif days_since_use < 3:
            score += 50

        elif days_since_use < 7:
            score += 20

    return score


# ============================================================
# CANDIDATE SELECTION
# ============================================================

def select_cycle_candidate(
    cycles: Sequence[Sequence[int]],
    relationships=None,
    rng=None,
) -> list[int] | None:
    """
    Select one cycle.

    Valid candidates with lower usage scores are preferred.

    Randomness is retained among the top few candidates so the
    exact same route is not selected every time.
    """

    rng = rng or random

    if not cycles:
        return None

    if not relationships:
        return list(
            rng.choice(cycles)
        )

    scored = sorted(
        (
            (
                list(cycle),
                score_cycle(
                    cycle,
                    relationships,
                ),
            )
            for cycle in cycles
        ),
        key=lambda item: item[1],
    )

    top_candidates = [
        cycle
        for cycle, _score in scored[
            : min(
                TOP_K_FOR_RANDOM_CHOICE,
                len(scored),
            )
        ]
    ]

    return list(
        rng.choice(top_candidates)
    )


# ============================================================
# OUTGOING CYCLE GENERATION
# ============================================================

def generate_outgoing_cycle(
    graph: dict[int, set[int]],
    participant_ids: Sequence[int],
    start_participant: int | None = None,
    relationships=None,
    rng=None,
) -> list[int] | None:
    """
    Generate a valid outgoing Hamiltonian cycle.

    The outgoing cycle:

    - contains everyone
    - follows only existing directed relationships
    - starts at the requested participant when supplied
    - otherwise chooses a random participant
    """

    rng = rng or random

    participant_ids = list(
        dict.fromkeys(participant_ids)
    )

    if len(participant_ids) < MIN_PARTICIPANTS:
        return None

    if start_participant is None:
        start_participant = (
            choose_starting_participant(
                participant_ids,
                rng=rng,
            )
        )

    if (
        start_participant is None
        or start_participant not in participant_ids
    ):
        return None

    candidates = search_hamiltonian_cycles(
        adjacency=graph,
        participant_ids=participant_ids,
        start_participant=start_participant,
        rng=rng,
    )

    if not candidates:
        return None

    return select_cycle_candidate(
        candidates,
        relationships,
        rng=rng,
    )


# ============================================================
# RETURN CYCLE GENERATION
# ============================================================

def generate_return_cycle(
    graph: dict[int, set[int]],
    participant_ids: Sequence[int],
    outgoing_cycle: Sequence[int],
    relationships=None,
    rng=None,
) -> list[int] | None:
    """
    Generate the return cycle.

    The return cycle:

    1. Contains every participant.
    2. Starts where the outgoing cycle started.
    3. Is directed.
    4. Uses existing relationships.
    5. Is not identical to the outgoing cycle.
    6. Is not the reverse of the outgoing cycle.
    7. NEVER reverses an outgoing edge.

    The critical rule is implemented by forbidding:

        reverse(outgoing_edges)
    """

    rng = rng or random

    if not outgoing_cycle:
        return None

    participant_ids = list(
        dict.fromkeys(participant_ids)
    )

    if len(participant_ids) < MIN_PARTICIPANTS:
        return None

    return_start = outgoing_cycle[0]

    outgoing_edges = cycle_to_edges(
        outgoing_cycle
    )

    forbidden_return_edges = frozenset(
        (
            to_id,
            from_id,
        )
        for from_id, to_id in outgoing_edges
    )

    candidates = search_hamiltonian_cycles(
        adjacency=graph,
        participant_ids=participant_ids,
        start_participant=return_start,
        forbidden_edges=forbidden_return_edges,
        rng=rng,
    )

    valid_candidates = []

    for candidate in candidates:

        if is_same_cycle(
            candidate,
            outgoing_cycle,
        ):
            continue

        if is_reverse_cycle(
            candidate,
            outgoing_cycle,
        ):
            continue

        if has_reverse_edge_conflict(
            outgoing_cycle,
            candidate,
        ):
            continue

        valid_candidates.append(
            candidate
        )

    if not valid_candidates:
        return None

    return select_cycle_candidate(
        valid_candidates,
        relationships,
        rng=rng,
    )


# ============================================================
# COMPLETE PAIR GENERATION
# ============================================================

def generate_valid_cycle_pair(
    participant_ids: Sequence[int],
    relationships: Iterable,
    start_participant_id: int | None = None,
    rng=None,
) -> dict[str, list[int]]:
    """
    Generate a strictly valid outgoing + return cycle pair.

    ============================================================
    CORE ALGORITHM RULES
    ============================================================

    RULE 1
        Every participant in the account must participate.

    RULE 2
        A cycle is directed.

    RULE 3
        Only relationships explicitly stored in the database
        may be used.

    RULE 4
        A participant may never pay themselves.

    RULE 5
        If A -> B exists, B -> A cannot be created as a
        relationship.

    RULE 6
        The outgoing route must be a Hamiltonian cycle.

    RULE 7
        The return route must also be a Hamiltonian cycle.

    RULE 8
        The outgoing route and return route must start at the
        same participant.

    RULE 9
        The return route cannot be identical to the outgoing
        route.

    RULE 10
        The return route cannot simply reverse the outgoing
        route.

    RULE 11
        The return route may NEVER contain the reverse of ANY
        outgoing edge.

        Outgoing:
            A -> B

        Forbidden on return:
            B -> A

    RULE 12
        A mathematically possible route is not enough.
        Every route must be validated against the actual
        relationship graph.

    RULE 13
        Usage history only affects candidate preference.
        It never allows an invalid relationship.

    RULE 14
        Randomness is used only among valid candidates.

    RULE 15
        If no valid pair exists, generation fails explicitly.
        The algorithm must never fabricate an edge.

    ============================================================
    """

    rng = rng or random

    participant_ids = list(
        dict.fromkeys(participant_ids)
    )

    # ---------------------------------------------------------
    # Participant validation
    # ---------------------------------------------------------

    if len(participant_ids) < MIN_PARTICIPANTS:
        raise ValueError(
            f"At least {MIN_PARTICIPANTS} participants are required "
            f"to generate a valid outgoing and return cycle."
        )

    if start_participant_id is not None:
        if start_participant_id not in participant_ids:
            raise ValueError(
                "Starting participant does not belong to this account."
            )

    # ---------------------------------------------------------
    # Relationship validation
    # ---------------------------------------------------------

    relationships = list(
        relationships or []
    )

    if not relationships:
        raise ValueError(
            "No relationships found. A cycle can only use "
            "existing directed relationships."
        )

    graph = build_graph(
        relationships
    )

    participant_set = set(
        participant_ids
    )

    # ---------------------------------------------------------
    # Only consider relationships between participants
    # belonging to this cycle.
    # ---------------------------------------------------------

    usable_edges = {
        (from_id, to_id)
        for from_id, neighbors in graph.items()
        for to_id in neighbors
        if (
            from_id in participant_set
            and to_id in participant_set
        )
    }

    if not usable_edges:
        raise ValueError(
            "No usable directed relationships exist between "
            "the participants in this cycle."
        )

    # ---------------------------------------------------------
    # Determine possible starting participants.
    # ---------------------------------------------------------

    if start_participant_id is not None:
        starters = [
            start_participant_id
        ]

    else:
        starters = list(
            participant_ids
        )
        rng.shuffle(starters)

    # ---------------------------------------------------------
    # Search for a complete pair.
    # ---------------------------------------------------------

    pair_candidates: list[
        tuple[list[int], list[int], float]
    ] = []

    for starter in starters:

        outgoing_candidates = search_hamiltonian_cycles(
            adjacency=graph,
            participant_ids=participant_ids,
            start_participant=starter,
            rng=rng,
        )

        if not outgoing_candidates:
            continue

        # Prefer less-used outgoing relationships.
        scored_outgoing = sorted(
            (
                (
                    cycle,
                    score_cycle(
                        cycle,
                        relationships,
                    ),
                )
                for cycle in outgoing_candidates
            ),
            key=lambda item: item[1],
        )

        for outgoing_cycle, outgoing_score in scored_outgoing:

            # -------------------------------------------------
            # Critical rule:
            #
            # Every reverse outgoing edge is forbidden on the
            # return route.
            # -------------------------------------------------

            outgoing_edges = cycle_to_edges(
                outgoing_cycle
            )

            forbidden_return_edges = frozenset(
                (
                    to_id,
                    from_id,
                )
                for from_id, to_id
                in outgoing_edges
            )

            return_candidates = search_hamiltonian_cycles(
                adjacency=graph,
                participant_ids=participant_ids,
                start_participant=starter,
                forbidden_edges=forbidden_return_edges,
                rng=rng,
            )

            for return_cycle in return_candidates:

                if not validate_two_cycles(
                    graph=graph,
                    outgoing_cycle=outgoing_cycle,
                    return_cycle=return_cycle,
                    participant_ids=participant_ids,
                ):
                    continue

                return_score = score_cycle(
                    return_cycle,
                    relationships,
                )

                pair_candidates.append(
                    (
                        list(outgoing_cycle),
                        list(return_cycle),
                        outgoing_score + return_score,
                    )
                )

                if (
                    len(pair_candidates)
                    >= TOP_K_FOR_RANDOM_CHOICE
                ):
                    break

            if (
                len(pair_candidates)
                >= TOP_K_FOR_RANDOM_CHOICE
            ):
                break

        if pair_candidates:
            break

    # ---------------------------------------------------------
    # No valid pair
    # ---------------------------------------------------------

    if not pair_candidates:

        any_outgoing_exists = False

        for starter in starters:

            candidates = search_hamiltonian_cycles(
                adjacency=graph,
                participant_ids=participant_ids,
                start_participant=starter,
                rng=rng,
            )

            if candidates:
                any_outgoing_exists = True
                break

        if not any_outgoing_exists:
            raise ValueError(
                "No valid directed outgoing cycle exists for the "
                "current relationships. Every movement must follow "
                "an existing relationship."
            )

        raise ValueError(
            "A valid outgoing cycle exists, but no valid return "
            "cycle can be created. The return cycle must be "
            "structurally different and must not reverse any "
            "outgoing relationship. Add additional directed "
            "relationships between participants."
        )

    # ---------------------------------------------------------
    # Select among the best valid pairs.
    # ---------------------------------------------------------

    pair_candidates.sort(
        key=lambda item: item[2]
    )

    best_pairs = pair_candidates[
        : min(
            TOP_K_FOR_RANDOM_CHOICE,
            len(pair_candidates),
        )
    ]

    outgoing_cycle, return_cycle, _score = (
        rng.choice(best_pairs)
    )

    # ---------------------------------------------------------
    # Final defensive validation.
    #
    # Never return a pair that has not passed the complete
    # validation layer.
    # ---------------------------------------------------------

    if not validate_two_cycles(
        graph=graph,
        outgoing_cycle=outgoing_cycle,
        return_cycle=return_cycle,
        participant_ids=participant_ids,
    ):
        raise RuntimeError(
            "Internal cycle-engine error: generated cycle pair "
            "failed final validation."
        )

    return {
        "outgoing_cycle": outgoing_cycle,
        "return_cycle": return_cycle,
    }


# ============================================================
# DISPLAY HELPER
# ============================================================

def display_cycle(
    label: str,
    cycle: Sequence[int] | None,
) -> None:
    """
    Print a cycle in a readable format.
    """

    print(
        f"\n{label}:"
    )

    if cycle:
        print(
            format_cycle(cycle)
        )
    else:
        print(
            "No valid cycle found."
        )