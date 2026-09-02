import uuid
from decimal import Decimal
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Account, Cycle
from app.services.cycle_service import (
    create_cycle,
    get_all_cycles,
    get_cycle,
)

client = TestClient(app)


def test_per_account_continuous_cycle_numbering():
    db = SessionLocal()
    try:
        # Create two distinct accounts
        account1 = Account(name=f"Org A {uuid.uuid4().hex[:6]}")
        account2 = Account(name=f"Org B {uuid.uuid4().hex[:6]}")
        db.add_all([account1, account2])
        db.commit()
        db.refresh(account1)
        db.refresh(account2)

        # Account 1 creates cycle 1, 2
        c1_a = create_cycle(db, account1.id)
        c2_a = create_cycle(db, account1.id)
        assert c1_a.cycle_number == 1
        assert c2_a.cycle_number == 2

        # Account 2 creates cycle 1
        c1_b = create_cycle(db, account2.id)
        assert c1_b.cycle_number == 1

        # Account 1 creates cycle 3 (must be 3, continuous, despite Account 2 creating a cycle in between)
        c3_a = create_cycle(db, account1.id)
        assert c3_a.cycle_number == 3

        # Account 2 creates cycle 2
        c2_b = create_cycle(db, account2.id)
        assert c2_b.cycle_number == 2

        # Verify get_cycle by integer ID and by UUID string
        fetched_by_id = get_cycle(db, c1_a.id)
        assert fetched_by_id is not None
        assert fetched_by_id.id == c1_a.id
        assert fetched_by_id.cycle_number == 1

        fetched_by_uuid = get_cycle(db, c1_a.uuid)
        assert fetched_by_uuid is not None
        assert fetched_by_uuid.id == c1_a.id
        assert fetched_by_uuid.cycle_number == 1

        # Verify API list endpoint returns cycles with cycle_number
        res_a = client.get(f"/cycles/account/{account1.id}")
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert len(data_a) == 3
        # Should be ordered descending: 3, 2, 1
        assert [c["cycle_number"] for c in data_a] == [3, 2, 1]

        res_b = client.get(f"/cycles/account/{account2.id}")
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert len(data_b) == 2
        assert [c["cycle_number"] for c in data_b] == [2, 1]

        # Verify API get endpoint by ID returns cycle_number and uuid
        res_single = client.get(f"/cycles/{c3_a.id}")
        assert res_single.status_code == 200
        single_data = res_single.json()
        assert single_data["cycle_number"] == 3
        assert single_data["uuid"] == c3_a.uuid
        assert single_data["account_id"] == account1.id

    finally:
        db.close()
