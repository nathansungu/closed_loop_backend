from sqlalchemy import select

from app.database import SessionLocal
from app.models import Account, Participant

from app.services.relationship_service import (
    get_all_relationships,
)

from app.services.cycle_engine import (
    build_graph,
    generate_outgoing_cycle,
    generate_return_cycle,
    validate_two_cycles,
    find_all_full_cycles,
    format_cycle,
)


def test_database_cycle():

    db = SessionLocal()

    try:

        # =================================================
        # 1. GET PARTICIPANTS FOR ACCOUNT 1
        # =================================================

        account = db.get(Account, 1)
        if not account:
            participants = db.execute(select(Participant)).scalars().all()
            account_id = participants[0].account_id if participants else 1
        else:
            account_id = account.id

        participants = db.execute(
            select(Participant).where(Participant.account_id == account_id)
        ).scalars().all()

        participant_ids = [participant.id for participant in participants]

        if not participant_ids:

            print("\nNo participants found.")

            return

        # =================================================
        # 2. GET RELATIONSHIPS
        # =================================================

        p_set = set(participant_ids)
        relationships = [
            r for r in get_all_relationships(db)
            if r.from_participant_id in p_set and r.to_participant_id in p_set
        ]

        # =================================================
        # 3. BUILD GRAPH
        # =================================================

        graph = build_graph(relationships)

        # =================================================
        # PARTICIPANTS
        # =================================================

        print("\n" + "=" * 60)
        print("PARTICIPANTS")
        print("=" * 60)

        print(participant_ids)

        # =================================================
        # RELATIONSHIPS
        # =================================================

        print("\n" + "=" * 60)
        print("EXISTING RELATIONSHIPS")
        print("=" * 60)

        if relationships:

            for relationship in relationships:

                print(
                    f"{relationship.from_participant_id}" f" → " f"{relationship.to_participant_id}"
                )

        else:

            print("No relationships found.")

        # =================================================
        # 4. GENERATE OUTGOING ROUND
        # =================================================

        outgoing_cycle = generate_outgoing_cycle(
            graph,
            participant_ids,
            relationships=relationships,
        )

        print("\n" + "=" * 60)
        print("OUTGOING ROUND")
        print("=" * 60)

        if outgoing_cycle:

            print(format_cycle(outgoing_cycle))

        else:

            print("No valid outgoing cycle found.")

            return

        # =================================================
        # OUTGOING INFORMATION
        # =================================================

        outgoing_starter = outgoing_cycle[0]

        outgoing_last_receiver = outgoing_cycle[-1]

        print(f"\nOutgoing starter: " f"{outgoing_starter}")

        print(f"Last person receiving " f"the outgoing round: " f"{outgoing_last_receiver}")

        # =================================================
        # 5. GENERATE RETURN ROUND
        # =================================================

        return_cycle = generate_return_cycle(
            graph,
            participant_ids,
            outgoing_cycle,
            relationships,
        )

        print("\n" + "=" * 60)
        print("RETURN ROUND")
        print("=" * 60)

        if return_cycle:

            print(format_cycle(return_cycle))

        else:

            print("No valid different return cycle found.")

        # =================================================
        # 6. VALIDATE BOTH ROUNDS
        # =================================================

        both_valid = validate_two_cycles(
            graph,
            outgoing_cycle,
            return_cycle,
            participant_ids,
        )

        print("\n" + "=" * 60)
        print("CYCLE VALIDATION")
        print("=" * 60)

        print(f"Outgoing cycle exists: " f"{outgoing_cycle is not None}")

        print(f"Return cycle exists: " f"{return_cycle is not None}")

        print(f"Two-cycle validation: " f"{both_valid}")

        # =================================================
        # 7. VERIFY RETURN STARTER
        # =================================================

        print("\n" + "=" * 60)
        print("RETURN STARTER CHECK")
        print("=" * 60)

        return_starter_correct = False

        if return_cycle:

            return_starter = return_cycle[0]

            print(f"Outgoing starter participant: " f"{outgoing_starter}")

            print(f"Return starter participant: " f"{return_starter}")

            return_starter_correct = outgoing_starter == return_starter

            print(f"Correct return starter: " f"{return_starter_correct}")

        else:

            print("Cannot check return starter " "because no return cycle exists.")

        # =================================================
        # 8. SHOW THE TWO ROUNDS TOGETHER
        # =================================================

        print("\n" + "=" * 60)
        print("ROUND SUMMARY")
        print("=" * 60)

        print("\nOutgoing:")

        print(format_cycle(outgoing_cycle))

        print("\nReturn:")

        if return_cycle:

            print(format_cycle(return_cycle))

        else:

            print("No return cycle.")

        # =================================================
        # 9. SHOW ALL POSSIBLE FULL CYCLES
        # =================================================

        all_cycles = find_all_full_cycles(
            graph,
            participant_ids,
        )

        print("\n" + "=" * 60)
        print(f"ALL POSSIBLE FULL CYCLES " f"({len(all_cycles)})")
        print("=" * 60)

        if all_cycles:

            for index, cycle in enumerate(
                all_cycles,
                start=1,
            ):

                print(f"{index}. " f"{format_cycle(cycle)}")

        else:

            print("No full cycles found.")

        # =================================================
        # 10. FINAL RESULT
        # =================================================

        print("\n" + "=" * 60)
        print("FINAL RESULT")
        print("=" * 60)

        # -------------------------------------------------
        # Rule 10:
        #
        # Return round starts with the same participant
        # who started the outgoing round.
        # -------------------------------------------------

        if return_starter_correct:

            print("SUCCESS")

            print(
                "\nThe return round correctly starts "
                "with the same participant who started "
                "the outgoing round."
            )

        else:

            print("FAILED")

            print(
                "\nThe return round does not start "
                "with the outgoing starter."
            )

        # =================================================
        # ADDITIONAL VALIDATION INFORMATION
        # =================================================

        print("\n" + "=" * 60)
        print("ADDITIONAL VALIDATION")
        print("=" * 60)

        if both_valid:

            print("The two cycles passed " "two-cycle validation.")

        else:

            print("The two cycles did NOT pass " "two-cycle validation.")

            print("\nNOTE:" "\nThis is separate from the " "return-starter rule.")

    finally:

        db.close()


if __name__ == "__main__":
    test_database_cycle()
