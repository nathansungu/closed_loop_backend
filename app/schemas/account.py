from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    name: str


class AccountUpdate(BaseModel):
    name: str


class AccountResponse(BaseModel):
    id: int
    uuid: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
