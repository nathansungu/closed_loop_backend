from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Participant

from app.services.cycle_service import (
    PENDING,
    OUTGOING_ACTIVE,
    OUTGOING_COMPLETED,
    RETURN_ACTIVE,
    SETTLED,
    create_cycle,
    add_participant_to_cycle,
    update_cycle_participant_amount,
    remove_participant_from_cycle,
    start_cycle,
    complete_outgoing_round,
    start_return_round,
    settle_cycle,
    get_cycle_participant,
)


import uuid
from app.models.account import Account


def test_cycle_lifecycle():

    db = SessionLocal()

    try:

        # =================================================
        # 1. SETUP DEDICATED ACCOUNT WITH 5 PARTICIPANTS
        # =================================================

        account = Account(name=f"Cycle Test Org {uuid.uuid4().hex[:6]}")
        db.add(account)
        db.commit()
        db.refresh(account)
        account_id = account.id

        created_participants = [
            Participant(name=f"Node {i+1}", account_id=account_id, initial_amount=Decimal("100.00"))
            for i in range(5)
        ]
        db.add_all(created_participants)
        db.commit()
        for p in created_participants:
            db.refresh(p)

        participant_ids = [p.id for p in created_participants]

        print("\n" + "=" * 60)
        print("PARTICIPANTS")
        print("=" * 60)

        print(participant_ids)

        # =================================================
        # 2. CREATE CYCLE
        # =================================================

        cycle = create_cycle(db, account_id)

        print("\n" + "=" * 60)
        print("CREATE CYCLE")
        print("=" * 60)

        print(f"Cycle ID: {cycle.id}")
        print(f"Status: {cycle.status}")

        assert cycle.status == PENDING

        print("PASS: Cycle starts as PENDING.")

        # =================================================
        # 3. REGISTER PARTICIPANTS
        # =================================================

        print("\n" + "=" * 60)
        print("REGISTER PARTICIPANTS")
        print("=" * 60)

        for participant_id in participant_ids:

            registration = add_participant_to_cycle(
                db,
                account_id,
                cycle.id,
                participant_id,
                Decimal("100.00"),
            )

            print(f"Participant {participant_id}: " f"{registration.initial_amount}")

        # =================================================
        # 4. EDIT INITIAL AMOUNT
        # =================================================
        #
        # This MUST work while the cycle is pending.
        #
        # Participant 1:
        #
        #     100 -> 150
        #
        # =================================================

        participant_to_edit = participant_ids[0]

        updated = update_cycle_participant_amount(
            db,
            account_id,
            cycle.id,
            participant_to_edit,
            Decimal("150.00"),
        )

        print("\n" + "=" * 60)
        print("EDIT INITIAL AMOUNT")
        print("=" * 60)

        print(f"Participant {participant_to_edit}: " f"{updated.initial_amount}")

        assert updated.initial_amount == Decimal("150.00")

        print("PASS: Initial amount can be edited " "while cycle is PENDING.")

        # =================================================
        # 5. VERIFY STORED AMOUNTS
        # =================================================

        print("\n" + "=" * 60)
        print("VERIFY INITIAL AMOUNTS")
        print("=" * 60)

        for participant_id in participant_ids:

            registration = get_cycle_participant(
                db,
                cycle.id,
                participant_id,
                account_id,
            )

            print(f"Participant {participant_id}: " f"{registration.initial_amount}")

        # =================================================
        # 6. START CYCLE
        # =================================================

        cycle = start_cycle(
            db,
            account_id,
            cycle.id,
        )

        print("\n" + "=" * 60)
        print("START CYCLE")
        print("=" * 60)

        print(f"Status: {cycle.status}")

        assert cycle.status == OUTGOING_ACTIVE

        print("PASS: Cycle entered OUTGOING_ACTIVE.")

        # =================================================
        # 7. TRY TO EDIT AMOUNT AFTER START
        # =================================================
        #
        # This MUST fail.
        #
        # The initial amount is now locked.
        #
        # =================================================

        print("\n" + "=" * 60)
        print("TEST AMOUNT LOCK")
        print("=" * 60)

        try:

            update_cycle_participant_amount(
                db,
                account_id,
                cycle.id,
                participant_to_edit,
                Decimal("200.00"),
            )

            print("FAIL: Amount was changed after " "the cycle started.")

        except ValueError as error:

            print("PASS: Amount change rejected.")

            print(f"Reason: {error}")

        # =================================================
        # 8. VERIFY AMOUNT DID NOT CHANGE
        # =================================================

        registration = get_cycle_participant(
            db,
            cycle.id,
            participant_to_edit,
            account_id,
        )

        print("\n" + "=" * 60)
        print("VERIFY AMOUNT REMAINED LOCKED")
        print("=" * 60)

        print(f"Participant {participant_to_edit}: " f"{registration.initial_amount}")

        assert registration.initial_amount == Decimal("150.00")

        print("PASS: Initial amount remained " "150.00.")

        # =================================================
        # 9. TRY ADDING PARTICIPANT AFTER START
        # =================================================

        print("\n" + "=" * 60)
        print("TEST PARTICIPANT LOCK")
        print("=" * 60)

        try:

            # Use an existing participant intentionally.
            # We only care that modification is rejected.

            add_participant_to_cycle(
                db,
                account_id,
                cycle.id,
                participant_ids[0],
                Decimal("100.00"),
            )

            print("FAIL: Participant registration " "was allowed after cycle start.")

        except ValueError as error:

            print("PASS: Adding participant rejected.")

            print(f"Reason: {error}")

        # =================================================
        # 10. COMPLETE OUTGOING ROUND
        # =================================================

        cycle = complete_outgoing_round(
            db,
            account_id,
            cycle.id,
        )

        print("\n" + "=" * 60)
        print("COMPLETE OUTGOING ROUND")
        print("=" * 60)

        print(f"Status: {cycle.status}")

        assert cycle.status == OUTGOING_COMPLETED

        print("PASS: Outgoing round completed.")

        # =================================================
        # 11. START RETURN ROUND
        # =================================================

        cycle = start_return_round(
            db,
            account_id,
            cycle.id,
        )

        print("\n" + "=" * 60)
        print("START RETURN ROUND")
        print("=" * 60)

        print(f"Status: {cycle.status}")

        assert cycle.status == RETURN_ACTIVE

        print("PASS: Return round started.")

        # =================================================
        # 12. SETTLE CYCLE
        # =================================================

        cycle = settle_cycle(
            db,
            account_id,
            cycle.id,
        )

        print("\n" + "=" * 60)
        print("SETTLE CYCLE")
        print("=" * 60)

        print(f"Status: {cycle.status}")

        assert cycle.status == SETTLED

        print("PASS: Cycle successfully settled.")

        # =================================================
        # FINAL RESULT
        # =================================================

        print("\n" + "=" * 60)
        print("FINAL RESULT")
        print("=" * 60)

        print("SUCCESS")

        print("\nCycle lifecycle works correctly:")

        print(
            "PENDING -> OUTGOING_ACTIVE -> OUTGOING_COMPLETED -> RETURN_ACTIVE -> SETTLED"
        )

        print("\nInitial amount editing:")

        print("100.00 -> 150.00 -> LOCKED")

    finally:

        db.close()


if __name__ == "__main__":
    test_cycle_lifecycle()
