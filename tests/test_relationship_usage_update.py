from decimal import Decimal
import uuid
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Account, Participant, Relationship
from app.services.cycle_service import (
    create_cycle,
    add_participant_to_cycle,
    start_cycle,
    complete_outgoing_round,
    start_return_round,
    settle_cycle,
    get_cycle_mapping_flow,
)


def test_relationship_usage_updates_on_cycle_lifecycle():
    db = SessionLocal()
    try:
        # 1. Setup account and 5 participants
        account = Account(name=f"Usage Test Org {uuid.uuid4().hex[:6]}")
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

        # 2. Setup a tournament directed network with valid Hamiltonian cycles
        # Ring 1: 0->1->2->3->4->0
        # Ring 2: 0->2->4->1->3->0
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
            Relationship(from_participant_id=src, to_participant_id=dst, times_used=0)
            for src, dst in edges
        ]
        db.add_all(rels)
        db.commit()

        # Check all relationships initially have times_used == 0
        for r in rels:
            db.refresh(r)
            assert r.times_used == 0
            assert r.first_used_at is None
            assert r.last_used_at is None

        # 3. Create and start cycle
        cycle = create_cycle(db, account_id)
        for pid in p_ids:
            add_participant_to_cycle(db, account_id, cycle.id, pid, Decimal("100.00"))

        start_cycle(db, account_id, cycle.id)

        # 4. Complete outgoing round
        complete_outgoing_round(db, account_id, cycle.id)

        # Query all relationships for this account
        updated_rels = db.execute(
            select(Relationship).where(
                Relationship.from_participant_id.in_(p_ids),
                Relationship.to_participant_id.in_(p_ids),
            )
        ).scalars().all()

        used_outgoing_rels = [r for r in updated_rels if r.times_used > 0]
        # Exactly 5 relationships in the outgoing cycle should have been used
        assert len(used_outgoing_rels) == 5
        for r in used_outgoing_rels:
            assert r.times_used == 1
            assert r.first_used_at is not None
            assert r.last_used_at is not None

        # 5. Start return round and settle cycle
        start_return_round(db, account_id, cycle.id)
        settle_cycle(db, account_id, cycle.id)

        updated_rels_after_settle = db.execute(
            select(Relationship).where(
                Relationship.from_participant_id.in_(p_ids),
                Relationship.to_participant_id.in_(p_ids),
            )
        ).scalars().all()

        total_times_used = sum(r.times_used for r in updated_rels_after_settle)
        # Outgoing (5) + Return (5) = 10 total usages recorded across relationships
        assert total_times_used == 10
        used_rels = [r for r in updated_rels_after_settle if r.times_used > 0]
        assert len(used_rels) >= 5
        for r in used_rels:
            assert r.first_used_at is not None
            assert r.last_used_at is not None

    finally:
        db.close()
