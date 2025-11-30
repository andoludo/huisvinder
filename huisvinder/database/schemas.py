from datetime import datetime

from sqlmodel import Field, SQLModel

from huisvinder.models import BaseHouse


class BaseHouseORM(SQLModel, BaseHouse, table=True):  # type: ignore
    __tablename__ = "basehouse"
    source: str = Field(index=True, primary_key=True)
    created_at: datetime = Field(primary_key=True, index=True)
    link: str = Field(primary_key=True, index=True)
