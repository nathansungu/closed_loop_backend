from decimal import Decimal
import uuid
from sqlalchemy import select
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Account, Participant, Relationship
from app.services.cycle_service import (
    get_account_relationships,
    generate_valid_cycle,
)

client = TestClient(app)


def test_toggle_relationship_status_api_and_service():
    db = SessionLocal()
    try:
        # 1. Setup account and 5 participants
        account = Account(name=f"Toggle Rel Test Org {uuid.uuid4().hex[:6]}")
        db.add(account)
        db.commit()
        db.refresh(account)
        account_id = account.id

        participants = [
            Participant(name=f"Node {i+1}", account_id=account_id, initial_amount=Decimal("100.00"), is_active=True)
            for i in range(5)
        ]
        db.add_all(participants)
        db.commit()
        for p in participants:
            db.refresh(p)

        p_ids = [p.id for p in participants]

        # 2. Setup standard tournament edges
        edges = [
            (p_ids[0], p_ids[1]),
            (p_ids[1], p_ids[2]),
            (p_ids[2], p_ids[3]),
            (p_ids[3], p_ids[4]),
            (p_ids[4], p_ids[0]),
            (p_ids[0], p_ids[2]),
            (p_ids[2], p_ids[4]),
            (p_ids[4], p_ids[1]),
            (p_ids[1], p_ids[3]),
            (p_ids[3], p_ids[0]),
        ]
        rels = [
            Relationship(from_participant_id=src, to_participant_id=dst, times_used=0, is_active=True)
            for src, dst in edges
        ]
        db.add_all(rels)
        db.commit()
        for r in rels:
            db.refresh(r)

        # 3. Initially all 10 relationships are active
        active_rels = get_account_relationships(db, account_id)
        assert len(active_rels) == 10

        # Can generate cycle
        gen_res = generate_valid_cycle(db, account_id)
        assert len(gen_res["outgoing_cycle"]) == 5

        # 4. Disable one relationship via PUT endpoint
        target_rel = rels[0]
        res = client.put(f"/relationships/{target_rel.id}", json={"is_active": False})
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == target_rel.id
        assert data["is_active"] is False

        # Verify DB reflects inactive status
        db.commit()
        db.refresh(target_rel)
        assert target_rel.is_active is False

        # Active relationships for account should now be 9
        active_rels_after_disable = get_account_relationships(db, account_id)
        assert len(active_rels_after_disable) == 9
        assert target_rel.id not in [r.id for r in active_rels_after_disable]

        # 5. Re-enable relationship via PUT endpoint
        res_enable = client.put(f"/relationships/{target_rel.id}", json={"is_active": True})
        assert res_enable.status_code == 200
        data_enable = res_enable.json()
        assert data_enable["is_active"] is True

        db.commit()
        db.refresh(target_rel)
        assert target_rel.is_active is True

        # Active relationships should be back to 10
        active_rels_after_enable = get_account_relationships(db, account_id)
        assert len(active_rels_after_enable) == 10

    finally:
        db.close()
