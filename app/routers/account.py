from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, User
from app.routers.auth import get_current_user, get_optional_current_user
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
)
from app.services.account_service import (
    create_account,
    delete_account,
    get_account_by_id,
    update_account,
)

router = APIRouter(
    prefix="/api/accounts",
    tags=["Accounts"],
)


@router.get(
    "/",
    response_model=list[AccountResponse],
)
def list_accounts(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    if current_user:
        result = db.execute(
            select(Account)
            .where(
                (Account.id == current_user.account_id) | (Account.owner_id == current_user.id)
            )
            .order_by(Account.id)
        )
        return result.scalars().all()
    result = db.execute(select(Account).order_by(Account.id))
    return result.scalars().all()


@router.post(
    "/",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    data: AccountCreate,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    clean_name = data.name.strip() if data.name else ""
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with your details: Chama name cannot be blank.",
        )
    owner_id = current_user.id if current_user else None
    new_account = create_account(db, clean_name, owner_id=owner_id)
    if current_user:
        current_user.account_id = new_account.id
        db.commit()
        db.refresh(current_user)
        db.refresh(new_account)
    return new_account


@router.post(
    "/{account_id}/switch",
    response_model=AccountResponse,
)
def switch_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_account_by_id(db, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chama not found",
        )
    if account.id != current_user.account_id and account.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to access this Chama.",
        )
    current_user.account_id = account.id
    db.commit()
    db.refresh(current_user)
    return account


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
)
def get(
    account_id: int,
    db: Session = Depends(get_db),
):
    account = get_account_by_id(db, account_id)

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    return account


@router.put(
    "/{account_id}",
    response_model=AccountResponse,
)
def update(
    account_id: int,
    data: AccountUpdate,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    account = get_account_by_id(db, account_id)

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if current_user:
        if account.id != current_user.account_id and account.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You cannot edit another organization's details.",
            )
        if current_user.role not in ("admin",):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator permissions required to update Chama details.",
            )

    clean_name = data.name.strip() if data.name else ""
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something is wrong with your details: Chama name cannot be blank.",
        )

    return update_account(db, account, clean_name)


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete(
    account_id: int,
    db: Session = Depends(get_db),
):
    account = get_account_by_id(db, account_id)

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    delete_account(db, account)
