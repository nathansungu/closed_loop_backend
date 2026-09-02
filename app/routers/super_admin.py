from datetime import datetime
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Cycle, CycleParticipant, Participant, Relationship, Transaction, User
from app.routers.auth import get_current_user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("super_admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Super Admin privileges required.",
        )
    return current_user


class SuperAdminMetricsResponse(BaseModel):
    total_accounts: int
    active_accounts: int
    inactive_accounts: int
    total_users: int
    active_users: int
    total_participants: int
    active_participants: int
    total_cycles: int
    settled_cycles: int
    active_cycles: int
    total_circulating_volume: float
    total_transactions: int
    system_status: str


class SuperAdminAccountItem(BaseModel):
    id: int
    uuid: str
    name: str
    is_active: bool
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    created_at: datetime
    total_users: int
    total_participants: int
    total_cycles: int
    settled_cycles: int
    active_cycles: int
    total_volume: float

    model_config = ConfigDict(from_attributes=True)


class SuperAdminUserItem(BaseModel):
    id: int
    uuid: str
    name: str
    email: str
    role: str
    is_active: bool
    account_id: int
    account_name: Optional[str] = None
    account_is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SuperAdminActivityItem(BaseModel):
    id: int
    account_id: int
    account_name: str
    cycle_number: int
    status: str
    participants_count: int
    created_at: datetime
    completed_at: Optional[datetime] = None


class AccountStatusUpdate(BaseModel):
    is_active: bool


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    role: str


class ImpersonateResponse(BaseModel):
    account_id: int
    account_name: str
    message: str


router = APIRouter(
    prefix="/super-admin",
    tags=["Super Admin"],
)


@router.get("/metrics", response_model=SuperAdminMetricsResponse)
def get_platform_metrics(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    total_accounts = db.execute(select(func.count(Account.id))).scalar_one() or 0
    active_accounts = (
        db.execute(select(func.count(Account.id)).where(Account.is_active.is_(True))).scalar_one() or 0
    )
    inactive_accounts = total_accounts - active_accounts

    total_users = db.execute(select(func.count(User.id))).scalar_one() or 0
    active_users = (
        db.execute(select(func.count(User.id)).where(User.is_active.is_(True))).scalar_one() or 0
    )

    total_participants = db.execute(select(func.count(Participant.id))).scalar_one() or 0
    active_participants = (
        db.execute(select(func.count(Participant.id)).where(Participant.is_active.is_(True))).scalar_one() or 0
    )

    total_cycles = db.execute(select(func.count(Cycle.id))).scalar_one() or 0
    settled_cycles = (
        db.execute(select(func.count(Cycle.id)).where(Cycle.status == "settled")).scalar_one() or 0
    )
    active_cycles = (
        db.execute(
            select(func.count(Cycle.id)).where(
                Cycle.status.in_(["outgoing_active", "outgoing_completed", "return_active"])
            )
        ).scalar_one()
        or 0
    )

    vol_sum = db.execute(select(func.coalesce(func.sum(Participant.initial_amount), 0))).scalar_one()
    total_transactions = db.execute(select(func.count(Transaction.id))).scalar_one() or 0

    return {
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "inactive_accounts": inactive_accounts,
        "total_users": total_users,
        "active_users": active_users,
        "total_participants": total_participants,
        "active_participants": active_participants,
        "total_cycles": total_cycles,
        "settled_cycles": settled_cycles,
        "active_cycles": active_cycles,
        "total_circulating_volume": float(vol_sum),
        "total_transactions": total_transactions,
        "system_status": "operational",
    }


@router.get("/accounts", response_model=list[SuperAdminAccountItem])
def list_all_accounts(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    accounts = db.execute(select(Account).order_by(Account.id.desc())).scalars().all()
    user_map = {u.id: u for u in db.execute(select(User)).scalars().all()}

    output = []
    for acc in accounts:
        owner = user_map.get(acc.owner_id) if acc.owner_id else None

        # Gather metrics for this account
        u_count = db.execute(
            select(func.count(User.id)).where(User.account_id == acc.id)
        ).scalar_one() or 0

        p_count = db.execute(
            select(func.count(Participant.id)).where(Participant.account_id == acc.id)
        ).scalar_one() or 0

        c_count = db.execute(
            select(func.count(Cycle.id)).where(Cycle.account_id == acc.id)
        ).scalar_one() or 0

        settled_count = db.execute(
            select(func.count(Cycle.id)).where(
                Cycle.account_id == acc.id, Cycle.status == "settled"
            )
        ).scalar_one() or 0

        active_c_count = db.execute(
            select(func.count(Cycle.id)).where(
                Cycle.account_id == acc.id,
                Cycle.status.in_(["outgoing_active", "outgoing_completed", "return_active"]),
            )
        ).scalar_one() or 0

        vol = db.execute(
            select(func.coalesce(func.sum(Participant.initial_amount), 0)).where(
                Participant.account_id == acc.id
            )
        ).scalar_one()

        output.append(
            {
                "id": acc.id,
                "uuid": acc.uuid,
                "name": acc.name,
                "is_active": getattr(acc, "is_active", True),
                "owner_id": acc.owner_id,
                "owner_name": owner.name if owner else None,
                "owner_email": owner.email if owner else None,
                "created_at": acc.created_at,
                "total_users": u_count,
                "total_participants": p_count,
                "total_cycles": c_count,
                "settled_cycles": settled_count,
                "active_cycles": active_c_count,
                "total_volume": float(vol),
            }
        )

    return output


@router.put("/accounts/{account_id}/status", response_model=SuperAdminAccountItem)
def toggle_account_status(
    account_id: int,
    data: AccountStatusUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    acc.is_active = data.is_active
    db.commit()
    db.refresh(acc)

    owner = db.get(User, acc.owner_id) if acc.owner_id else None
    u_count = db.execute(
        select(func.count(User.id)).where(User.account_id == acc.id)
    ).scalar_one() or 0
    p_count = db.execute(
        select(func.count(Participant.id)).where(Participant.account_id == acc.id)
    ).scalar_one() or 0
    c_count = db.execute(
        select(func.count(Cycle.id)).where(Cycle.account_id == acc.id)
    ).scalar_one() or 0
    settled_count = db.execute(
        select(func.count(Cycle.id)).where(
            Cycle.account_id == acc.id, Cycle.status == "settled"
        )
    ).scalar_one() or 0
    active_c_count = db.execute(
        select(func.count(Cycle.id)).where(
            Cycle.account_id == acc.id,
            Cycle.status.in_(["outgoing_active", "outgoing_completed", "return_active"]),
        )
    ).scalar_one() or 0
    vol = db.execute(
        select(func.coalesce(func.sum(Participant.initial_amount), 0)).where(
            Participant.account_id == acc.id
        )
    ).scalar_one()

    return {
        "id": acc.id,
        "uuid": acc.uuid,
        "name": acc.name,
        "is_active": acc.is_active,
        "owner_id": acc.owner_id,
        "owner_name": owner.name if owner else None,
        "owner_email": owner.email if owner else None,
        "created_at": acc.created_at,
        "total_users": u_count,
        "total_participants": p_count,
        "total_cycles": c_count,
        "settled_cycles": settled_count,
        "active_cycles": active_c_count,
        "total_volume": float(vol),
    }


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account_by_super_admin(
    account_id: int,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    db.delete(acc)
    db.commit()
    return None


@router.get("/users", response_model=list[SuperAdminUserItem])
def list_all_users(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    users = db.execute(select(User).order_by(User.id.desc())).scalars().all()
    account_map = {a.id: a for a in db.execute(select(Account)).scalars().all()}

    output = []
    for u in users:
        acc = account_map.get(u.account_id)
        output.append(
            {
                "id": u.id,
                "uuid": u.uuid,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "account_id": u.account_id,
                "account_name": acc.name if acc else "Unknown",
                "account_is_active": getattr(acc, "is_active", True) if acc else False,
                "created_at": u.created_at,
                "updated_at": u.updated_at,
            }
        )

    return output


@router.put("/users/{user_id}/status", response_model=SuperAdminUserItem)
def toggle_user_status(
    user_id: int,
    data: UserStatusUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == current_user.id and not data.is_active:
        raise HTTPException(
            status_code=400,
            detail="Super Admin cannot disable their own account.",
        )

    target.is_active = data.is_active
    db.commit()
    db.refresh(target)

    acc = db.get(Account, target.account_id)
    return {
        "id": target.id,
        "uuid": target.uuid,
        "name": target.name,
        "email": target.email,
        "role": target.role,
        "is_active": target.is_active,
        "account_id": target.account_id,
        "account_name": acc.name if acc else "Unknown",
        "account_is_active": getattr(acc, "is_active", True) if acc else False,
        "created_at": target.created_at,
        "updated_at": target.updated_at,
    }


@router.put("/users/{user_id}/role", response_model=SuperAdminUserItem)
def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    valid_roles = {"super_admin", "admin", "member", "viewer"}
    clean_role = data.role.lower().strip()
    if clean_role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of {valid_roles}",
        )

    target.role = clean_role
    db.commit()
    db.refresh(target)

    acc = db.get(Account, target.account_id)
    return {
        "id": target.id,
        "uuid": target.uuid,
        "name": target.name,
        "email": target.email,
        "role": target.role,
        "is_active": target.is_active,
        "account_id": target.account_id,
        "account_name": acc.name if acc else "Unknown",
        "account_is_active": getattr(acc, "is_active", True) if acc else False,
        "created_at": target.created_at,
        "updated_at": target.updated_at,
    }


@router.post("/impersonate/{account_id}", response_model=ImpersonateResponse)
def impersonate_account(
    account_id: int,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    return {
        "account_id": acc.id,
        "account_name": acc.name,
        "message": f"Successfully switched control to Chama '{acc.name}'.",
    }


@router.get("/activity", response_model=list[SuperAdminActivityItem])
def get_recent_activity(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    cycles = db.execute(
        select(Cycle).order_by(Cycle.id.desc()).limit(20)
    ).scalars().all()
    account_map = {a.id: a for a in db.execute(select(Account)).scalars().all()}

    output = []
    for c in cycles:
        acc = account_map.get(c.account_id)
        p_count = db.execute(
            select(func.count(CycleParticipant.id)).where(CycleParticipant.cycle_id == c.id)
        ).scalar_one() or 0

        output.append(
            {
                "id": c.id,
                "account_id": c.account_id,
                "account_name": acc.name if acc else f"Chama #{c.account_id}",
                "cycle_number": getattr(c, "cycle_number", c.id),
                "status": c.status,
                "participants_count": p_count,
                "created_at": c.created_at,
                "completed_at": c.completed_at,
            }
        )

    return output
