from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account


def create_account(
    db: Session,
    name: str,
    owner_id: Optional[int] = None,
):
    account = Account(
        uuid=str(uuid.uuid4()),
        name=name,
        owner_id=owner_id,
    )

    db.add(account)
    db.commit()
    db.refresh(account)

    return account


def get_account_by_id(
    db: Session,
    account_id: int,
):
    return db.get(
        Account,
        account_id,
    )


def get_account_by_uuid(
    db: Session,
    account_uuid: str,
):
    result = db.execute(
        select(Account).where(
            Account.uuid == account_uuid,
        )
    )

    return result.scalar_one_or_none()


def update_account(
    db: Session,
    account: Account,
    name: str,
):
    account.name = name

    db.commit()
    db.refresh(account)

    return account


def delete_account(
    db: Session,
    account: Account,
):
    db.delete(account)
    db.commit()
