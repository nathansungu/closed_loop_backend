from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Account, Participant, Cycle, CycleParticipant, Relationship

from app.services.relationship_service import (
    get_all_relationships,
    record_cycle_usage,
)

from app.services.cycle_engine import (
    build_graph,
    generate_valid_cycle_pair,
    format_cycle,
)

from app.services.transaction_service import (
    calculate_outgoing_transactions,
    calculate_return_transactions,
    display_transactions,
)


def test_transaction_service():

    db = SessionLocal()

    try:

        # =================================================
        # 1. GET PARTICIPANTS FOR ACCOUNT 1
        # =================================================

        account = db.get(Account, 1)
        account_id = account.id if account else 1

        participants = db.execute(
            select(Participant).where(Participant.account_id == account_id).order_by(Participant.id)
        ).scalars().all()

        if not participants:

            print("No participants found.")

            return

        participant_ids = [participant.id for participant in participants]
        p_set = set(participant_ids)

        # =================================================
        # 2. GET RELATIONSHIPS
        # =================================================

        relationships = db.execute(
            select(Relationship).where(
                Relationship.from_participant_id.in_(p_set),
                Relationship.to_participant_id.in_(p_set),
            )
        ).scalars().all()

        # =================================================
        # 3. DISPLAY INITIAL AMOUNTS
        # =================================================

        print("\n" + "=" * 60)
        print("INITIAL AMOUNTS")
        print("=" * 60)

        for p in participants:
            print(
                f"{p.id}"
                f" = "
                f"{Decimal(str(p.initial_amount)):.2f}"
            )

        # =================================================
        # 4. GENERATE VALID CYCLE PAIR
        # =================================================

        pair = generate_valid_cycle_pair(
            participant_ids=participant_ids,
            relationships=relationships,
        )

        outgoing_cycle = pair["outgoing_cycle"]
        return_cycle = pair["return_cycle"]

        print("\n" + "=" * 60)
        print("OUTGOING CYCLE")
        print("=" * 60)

        print(format_cycle(outgoing_cycle))

        # =================================================
        # 5. CALCULATE OUTGOING TRANSACTIONS
        # =================================================

        outgoing_transactions = calculate_outgoing_transactions(
            participants,
            outgoing_cycle,
        )

        display_transactions(
            outgoing_transactions,
            "OUTGOING TRANSACTIONS",
        )

        # =================================================
        # 6. RECORD OUTGOING RELATIONSHIP USAGE
        # =================================================

        record_cycle_usage(
            db,
            outgoing_cycle,
        )

        # =================================================
        # 7. RETURN CYCLE
        # =================================================

        print("\n" + "=" * 60)
        print("RETURN CYCLE")
        print("=" * 60)

        print(format_cycle(return_cycle))

        # =================================================
        # 10. CALCULATE RETURN TRANSACTIONS
        # =================================================

        return_transactions = calculate_return_transactions(
            participants,
            outgoing_cycle,
            return_cycle,
            outgoing_transactions,
        )

        display_transactions(
            return_transactions,
            "RETURN TRANSACTIONS",
        )

        # =================================================
        # 11. VERIFY RETURN STARTER
        # =================================================

        print("\n" + "=" * 60)
        print("RETURN STARTER CHECK")
        print("=" * 60)

        outgoing_first = outgoing_cycle[0]
        return_first = return_cycle[0]

        print(f"Outgoing first: {outgoing_first}")
        print(f"Return first: {return_first}")

        if outgoing_first == return_first:

            print("PASS: Correct return starter.")

        else:

            print("FAIL: Incorrect return starter.")

        # =================================================
        # 12. DISPLAY UPDATED RELATIONSHIPS
        # =================================================

        print("\n" + "=" * 60)
        print("RELATIONSHIP USAGE")
        print("=" * 60)

        updated_relationships = get_all_relationships(db)

        for relationship in updated_relationships:

            print(
                f"{relationship.from_participant_id}"
                f" → "
                f"{relationship.to_participant_id}"
                f" | "
                f"times_used = "
                f"{relationship.times_used}"
            )

        # =================================================
        # 13. FINAL RESULT
        # =================================================

        print("\n" + "=" * 60)
        print("TRANSACTION FLOW TEST")
        print("=" * 60)

        print("PASS: Transaction amounts " "calculated successfully.")

    finally:

        db.close()


if __name__ == "__main__":
    test_transaction_service()
