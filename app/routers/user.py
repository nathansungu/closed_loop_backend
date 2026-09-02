from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account
from app.models.user import User
from app.routers.auth import get_current_user, hash_password, require_admin

router = APIRouter(
    prefix="/users",
    tags=["Users & Team Management"],
)


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "member"  # 'admin' | 'member' | 'viewer'


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    uuid: str
    name: str
    email: str
    role: str
    account_id: int
    is_active: bool
    created_at: datetime
    organization_name: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=list[UserResponse])
def list_team_members(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List all users belonging to the current authenticated user's organization.
    Users from other organizations are never visible.
    """
    account = db.get(Account, current_user.account_id)
    org_name = account.name if account else "Organization"

    users = (
        db.execute(
            select(User)
            .where(User.account_id == current_user.account_id)
            .order_by(User.created_at.asc())
        )
        .scalars()
        .all()
    )

    return [
        {
            "id": u.id,
            "uuid": u.uuid,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "account_id": u.account_id,
            "is_active": u.is_active,
            "created_at": u.created_at,
            "organization_name": org_name,
        }
        for u in users
    ]


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_team_member(
    data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Organization Admins can create new team members with email, password, and role.
    """
    clean_name = data.name.strip() if data.name else ""
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with the provided details: Full name is required.",
        )

    clean_email = data.email.lower().strip() if data.email else ""
    if not clean_email or "@" not in clean_email or "." not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with the provided details: Please provide a valid email address.",
        )

    if not data.password or len(data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with the provided details: Password must be at least 6 characters long.",
        )

    existing = db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with the provided details: A user with this email already exists.",
        )

    valid_roles = {"admin", "member", "viewer"}
    role = data.role.lower().strip()
    if role not in valid_roles:
        role = "member"

    user = User(
        name=clean_name,
        email=clean_email,
        password_hash=hash_password(data.password),
        account_id=current_user.account_id,
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    account = db.get(Account, current_user.account_id)
    org_name = account.name if account else "Organization"

    return {
        "id": user.id,
        "uuid": user.uuid,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "account_id": user.account_id,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "organization_name": org_name,
    }


@router.patch("/{user_id}", response_model=UserResponse)
def update_team_member(
    user_id: int,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Organization Admins can update roles, enable/disable users, or reset details.
    """
    user = db.get(User, user_id)
    if not user or user.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in your organization.",
        )

    # Prevent admin from disabling or demoting themselves if they are the only admin
    if user.id == current_user.id:
        if data.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot disable your own active account.",
            )
        if data.role and data.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot change your own admin role. Another admin must do this.",
            )

    if data.name is not None and data.name.strip():
        user.name = data.name.strip()

    if data.role is not None:
        valid_roles = {"admin", "member", "viewer"}
        r = data.role.lower().strip()
        if r in valid_roles:
            user.role = r

    if data.is_active is not None:
        user.is_active = data.is_active

    if data.password is not None and data.password.strip():
        user.password_hash = hash_password(data.password.strip())

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    account = db.get(Account, current_user.account_id)
    org_name = account.name if account else "Organization"

    return {
        "id": user.id,
        "uuid": user.uuid,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "account_id": user.account_id,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "organization_name": org_name,
    }


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_member(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Remove a team member from the organization.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    user = db.get(User, user_id)
    if not user or user.account_id != current_user.account_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in your organization.",
        )

    db.delete(user)
    db.commit()
