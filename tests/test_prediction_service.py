from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Account, Participant, Relationship

from app.services.prediction_service import (
    predict_cycles,
    predict_cycles_for_week,
    predict_cycles_for_month,
    predict_cycles_for_year,
)

from app.services.cycle_engine import (
    build_graph,
    validate_cycle,
    validate_two_cycles,
)


def print_separator():
    print("\n" + "=" * 70)


def print_prediction(prediction):
    print(f"\nPERIOD {prediction.period}")
    print(f"DATE: {prediction.date.strftime('%Y-%m-%d')}")

    print(
        "OUTGOING: "
        + " → ".join(map(str, prediction.outgoing_cycle))
        + f" → {prediction.outgoing_cycle[0]}"
    )

    print(
        "RETURN:   "
        + " → ".join(map(str, prediction.return_cycle))
        + f" → {prediction.return_cycle[0]}"
    )

    print(f"OUTGOING STARTER: " f"{prediction.outgoing_cycle[0]}")

    print(f"RETURN STARTER:   " f"{prediction.return_cycle[0]}")


def test_prediction_service():

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

        if not relationships:
            print("No relationships found.")
            return

        # =================================================
        # 3. DISPLAY CURRENT RELATIONSHIP USAGE
        # =================================================

        print_separator()

        print("CURRENT RELATIONSHIP USAGE")

        print_separator()

        original_usage = {}

        for relationship in relationships:

            key = (
                relationship.from_participant_id,
                relationship.to_participant_id,
            )

            original_usage[key] = relationship.times_used or 0

            print(
                f"{relationship.from_participant_id}"
                f" → "
                f"{relationship.to_participant_id}"
                f" : "
                f"{relationship.times_used or 0}"
            )

        # =================================================
        # 4. PREDICT ONE WEEK
        # =================================================

        print_separator()

        print("7-DAY PREDICTION")

        print_separator()

        start_date = datetime.utcnow() + timedelta(days=1)

        predictions = predict_cycles_for_week(
            participant_ids=participant_ids,
            relationships=relationships,
            start_date=start_date,
        )

        if not predictions:

            print("No predictions generated.")
            return

        # =================================================
        # 5. DISPLAY PREDICTIONS
        # =================================================

        for prediction in predictions:

            print_prediction(prediction)

        # =================================================
        # 6. VALIDATE EVERY PREDICTION
        # =================================================

        print_separator()

        print("PREDICTION VALIDATION")

        print_separator()

        all_valid = True

        for prediction in predictions:

            graph = build_graph(relationships)

            valid_outgoing = validate_cycle(
                graph,
                prediction.outgoing_cycle,
                participant_ids,
            )

            valid_return = validate_cycle(
                graph,
                prediction.return_cycle,
                participant_ids,
            )

            valid_pair = validate_two_cycles(
                graph,
                prediction.outgoing_cycle,
                prediction.return_cycle,
                participant_ids,
            )

            same_starter = prediction.outgoing_cycle[0] == prediction.return_cycle[0]

            if not valid_outgoing:

                print(f"FAIL: Period {prediction.period} " f"has an invalid outgoing cycle.")

                all_valid = False

            if not valid_return:

                print(f"FAIL: Period {prediction.period} " f"has an invalid return cycle.")

                all_valid = False

            if not valid_pair:

                print(f"FAIL: Period {prediction.period} " f"failed two-cycle validation.")

                all_valid = False

            if not same_starter:

                print(
                    f"FAIL: Period {prediction.period} "
                    f"has different outgoing and return starters."
                )

                all_valid = False

        if all_valid:

            print("PASS: All predicted cycles are valid.")

        # =================================================
        # 7. CHECK RETURN STARTER RULE
        # =================================================

        print_separator()

        print("RETURN STARTER CHECK")

        print_separator()

        starter_valid = True

        for prediction in predictions:

            outgoing_first = prediction.outgoing_cycle[0]

            return_first = prediction.return_cycle[0]

            print(
                f"Period {prediction.period}: "
                f"Outgoing first = {outgoing_first}, "
                f"Return first = {return_first}"
            )

            if outgoing_first != return_first:

                starter_valid = False

        if starter_valid:

            print("PASS: Every return cycle starts " "with the outgoing starter.")

        else:

            print("FAIL: Return starter rule violated.")

        # =================================================
        # 8. CHECK PARTICIPANT COVERAGE
        # =================================================

        print_separator()

        print("PARTICIPANT COVERAGE CHECK")

        print_separator()

        coverage_valid = True

        expected = set(participant_ids)

        for prediction in predictions:

            outgoing_set = set(prediction.outgoing_cycle)

            return_set = set(prediction.return_cycle)

            if outgoing_set != expected:

                print(
                    f"FAIL: Period {prediction.period} "
                    f"outgoing cycle does not contain "
                    f"all participants."
                )

                coverage_valid = False

            if return_set != expected:

                print(
                    f"FAIL: Period {prediction.period} "
                    f"return cycle does not contain "
                    f"all participants."
                )

                coverage_valid = False

        if coverage_valid:

            print("PASS: Every prediction contains " "all participants.")

        # =================================================
        # 9. CHECK OUTGOING / RETURN DIFFERENCE
        # =================================================

        print_separator()

        print("ROUTE DIFFERENCE CHECK")

        print_separator()

        routes_valid = True

        for prediction in predictions:

            outgoing_edges = tuple(
                (
                    prediction.outgoing_cycle[i],
                    prediction.outgoing_cycle[(i + 1) % len(prediction.outgoing_cycle)],
                )
                for i in range(len(prediction.outgoing_cycle))
            )

            return_edges = tuple(
                (
                    prediction.return_cycle[i],
                    prediction.return_cycle[(i + 1) % len(prediction.return_cycle)],
                )
                for i in range(len(prediction.return_cycle))
            )

            if set(outgoing_edges) == set(return_edges):

                print(
                    f"FAIL: Period {prediction.period} "
                    f"uses the same route for outgoing "
                    f"and return."
                )

                routes_valid = False

        if routes_valid:

            print("PASS: Outgoing and return routes " "are different.")

        # =================================================
        # 10. CHECK REAL DATABASE WAS NOT MODIFIED
        # =================================================

        print_separator()

        print("DATABASE INTEGRITY CHECK")

        print_separator()

        db.expire_all()

        current_relationships = db.execute(select(Relationship)).scalars().all()

        database_unchanged = True

        for relationship in current_relationships:

            key = (
                relationship.from_participant_id,
                relationship.to_participant_id,
            )

            current_usage = relationship.times_used or 0

            original_value = original_usage.get(
                key,
                0,
            )

            if current_usage != original_value:

                print(
                    f"FAIL: Relationship "
                    f"{key[0]} → {key[1]} "
                    f"changed from "
                    f"{original_value} "
                    f"to "
                    f"{current_usage}"
                )

                database_unchanged = False

        if database_unchanged:

            print("PASS: Prediction did not modify " "real relationship usage.")

        # =================================================
        # 11. SUMMARY
        # =================================================

        print_separator()

        print("PREDICTION TEST SUMMARY")

        print_separator()

        print(f"Requested periods: 7")

        print(f"Generated periods: {len(predictions)}")

        print(f"Expected periods: 7")

        if len(predictions) == 7:

            print("PASS: All requested prediction " "periods were generated.")

        else:

            print("WARNING: Not all requested periods " "were generated.")

        if (
            all_valid
            and starter_valid
            and coverage_valid
            and routes_valid
            and database_unchanged
            and len(predictions) == 7
        ):

            print_separator()

            print("PASS: PREDICTION SERVICE TEST PASSED.")

            print_separator()

        else:

            print_separator()

            print("FAIL: PREDICTION SERVICE TEST FAILED.")

            print_separator()

    finally:

        db.close()


if __name__ == "__main__":
    test_prediction_service()
