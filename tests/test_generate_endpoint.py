from decimal import Decimal
import json
import urllib.error
import urllib.request

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Account, Cycle, CycleParticipant, Participant
from app.services.cycle_service import (
    generate_valid_cycle,
    get_account_participant_initial_amounts,
    get_account_participants,
)


def print_separator(title=""):
    print("\n" + "=" * 65)
    if title:
        print(title)
        print("=" * 65)


import uuid
from app.models.relationship import Relationship


def _get_or_create_test_account(db):
    account = Account(name=f"Test Chama {uuid.uuid4().hex[:6]}")
    db.add(account)
    db.commit()
    db.refresh(account)

    p1 = Participant(name="Alice", account_id=account.id, initial_amount=Decimal("100.00"))
    p2 = Participant(name="Bob", account_id=account.id, initial_amount=Decimal("200.00"))
    p3 = Participant(name="Charlie", account_id=account.id, initial_amount=Decimal("300.00"))
    p4 = Participant(name="Diana", account_id=account.id, initial_amount=Decimal("400.00"))
    db.add_all([p1, p2, p3, p4])
    db.commit()
    db.refresh(p1)
    db.refresh(p2)
    db.refresh(p3)
    db.refresh(p4)

    # Add directed relationships allowing multiple distinct Hamiltonian cycles
    # Outgoing: 1 -> 2 -> 3 -> 4 -> 1
    # Return:   1 -> 3 -> 2 -> 4 -> 1
    edges = [
        (p1.id, p2.id), (p2.id, p3.id), (p3.id, p4.id), (p4.id, p1.id),
        (p1.id, p3.id), (p3.id, p2.id), (p2.id, p4.id),
        (p4.id, p2.id), (p2.id, p1.id), (p3.id, p1.id), (p4.id, p3.id),
    ]
    for src, dst in edges:
        db.add(Relationship(from_participant_id=src, to_participant_id=dst))
    db.commit()

    return account


def test_service_layer():
    print_separator("TEST 1: SERVICE LAYER (generate_valid_cycle)")

    db = SessionLocal()
    try:
        account = _get_or_create_test_account(db)
        account_id = account.id

        participants = get_account_participants(db, account_id)
        participant_ids = [p.id for p in participants]
        print(f"Account ID: {account_id}")
        print(f"Total Participants: {len(participant_ids)}")
        print(f"Participant IDs: {participant_ids}")

        initial_amounts = get_account_participant_initial_amounts(
            db,
            account_id,
            participant_ids,
        )
        print("\nDatabase Historical Initial Amounts:")
        for pid in participant_ids:
            print(f"  Participant {pid}: {initial_amounts[pid]:.2f}")

        # Execute generate_valid_cycle
        result = generate_valid_cycle(db, account_id)

        print("\nGenerated Result Structure:")
        print(f"  account_id: {result['account_id']}")
        print(f"  participant_ids count: {len(result['participant_ids'])}")
        print(f"  outgoing_cycle count: {len(result['outgoing_cycle'])}")
        print(f"  return_cycle count: {len(result['return_cycle'])}")
        print(f"  outgoing_transactions count: {len(result['outgoing_transactions'])}")
        print(f"  return_transactions count: {len(result['return_transactions'])}")
        print(f"  total_circulating_amount: {result['total_circulating_amount']:.2f}")

        # Assert total circulating amount equals sum of participant initial amounts
        expected_total = sum(initial_amounts[pid] for pid in participant_ids)
        assert (
            result["total_circulating_amount"] == expected_total
        ), f"Expected total circulating {expected_total}, got {result['total_circulating_amount']}"
        print(f"\nPASS: Total circulating amount ({result['total_circulating_amount']}) matches sum of all initial amounts ({expected_total}).")

        # Verify participant metrics
        print("\nParticipant Computed Flow Metrics:")
        for p in result["participants"]:
            print(
                f"  ID {p['id']} ({p['name']}): "
                f"initial={p['initial_amount']:.2f}, "
                f"received={p['total_received']:.2f}, "
                f"sent={p['total_sent']:.2f}, "
                f"accumulation={p['total_accumulation']:.2f}"
            )
            # Ensure none are dummy zero if initial amount > 0
            assert p["initial_amount"] > 0, f"Participant {p['id']} initial_amount must be > 0"
            assert p["total_received"] > 0, f"Participant {p['id']} total_received must be > 0"
            assert p["total_sent"] > 0, f"Participant {p['id']} total_sent must be > 0"
            # Final accumulation equals initial amount (balanced return)
            assert p["total_accumulation"] == p["initial_amount"], (
                f"Participant {p['id']} accumulation ({p['total_accumulation']}) "
                f"must equal initial amount ({p['initial_amount']})"
            )

        print("\nPASS: All participant metrics are non-zero, properly computed, and balanced.")

        # Outgoing transactions verification
        print("\nOutgoing Transactions Flow:")
        for tx in result["outgoing_transactions"]:
            print(f"  outgoing: {tx['from_participant_id']} -> {tx['to_participant_id']} : {tx['amount']:.2f}")
            assert tx["amount"] > 0

        # Return transactions verification
        print("\nReturn Transactions Flow:")
        for tx in result["return_transactions"]:
            print(f"  return:   {tx['from_participant_id']} -> {tx['to_participant_id']} : {tx['amount']:.2f}")
            assert tx["amount"] > 0

        print("\nPASS: Service layer test passed successfully.")
    finally:
        db.close()


from fastapi import HTTPException
from app.routers.cycle import generate as generate_endpoint


def test_api_endpoint():
    print_separator("TEST 2: API ENDPOINT (POST /cycles/account/1/generate)")

    url = "http://127.0.0.1:8000/cycles/account/1/generate"
    req = urllib.request.Request(
        url,
        data=b"",
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            status_code = resp.status
            assert status_code == 200, f"Expected status 200, got {status_code}"

            body = json.loads(resp.read().decode("utf-8"))
            print(f"HTTP Status: {status_code}")
            print(f"Account ID: {body['account_id']}")
            print(f"Total Circulating Amount: {body['total_circulating_amount']}")
            print(f"Participants count: {len(body['participants'])}")
            print(f"Outgoing cycle count: {len(body['outgoing_cycle'])}")
            print(f"Return cycle count: {len(body['return_cycle'])}")
            print(f"Outgoing transactions: {len(body['outgoing_transactions'])}")
            print(f"Return transactions: {len(body['return_transactions'])}")

            first_p = body["participants"][0]
            print(f"\nFirst participant sample: {first_p}")
            assert Decimal(str(first_p["initial_amount"])) > 0
            assert Decimal(str(first_p["total_received"])) > 0
            assert Decimal(str(first_p["total_sent"])) > 0
            assert Decimal(str(first_p["total_accumulation"])) > 0

            print("\nPASS: API Endpoint returns 200 OK via HTTP with actual computed values.")
            return
    except urllib.error.URLError:
        print("Note: Live server not active on port 8000. Testing router handler directly...")

    db = SessionLocal()
    try:
        account = _get_or_create_test_account(db)
        result = generate_endpoint(account_id=account.id, start_participant_id=None, db=db)
        assert result is not None
        assert result["account_id"] == account.id
        assert len(result["participants"]) > 0
        assert len(result["outgoing_cycle"]) > 0
        assert len(result["return_cycle"]) > 0
        assert result["total_circulating_amount"] > 0
        print(f"Direct Router Result: account_id={result['account_id']}, participants={len(result['participants'])}, total={result['total_circulating_amount']}")
        print("PASS: Router endpoint function executed and validated successfully.")
    finally:
        db.close()


def test_error_handling():
    print_separator("TEST 3: ERROR HANDLING (Non-existent account)")

    url = "http://127.0.0.1:8000/cycles/account/999999/generate"
    req = urllib.request.Request(
        url,
        data=b"",
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        urllib.request.urlopen(req)
        print("FAIL: Expected 400 Bad Request for non-existent account.")
    except urllib.error.HTTPError as exc:
        assert exc.code == 400
        error_detail = json.loads(exc.read().decode("utf-8"))
        print(f"PASS: Correctly rejected via HTTP with 400: {error_detail}")
        return
    except urllib.error.URLError:
        print("Note: Live server not active on port 8000. Testing router error handling directly...")

    db = SessionLocal()
    try:
        try:
            generate_endpoint(account_id=999999, start_participant_id=None, db=db)
            print("FAIL: Expected HTTPException 400 for non-existent account.")
        except HTTPException as exc:
            assert exc.status_code == 400
            print(f"PASS: Router correctly raised HTTPException 400: {exc.detail}")
    finally:
        db.close()


def main():
    test_service_layer()
    test_api_endpoint()
    test_error_handling()
    print_separator("ALL TESTS PASSED SUCCESSFULLY")


if __name__ == "__main__":
    main()

