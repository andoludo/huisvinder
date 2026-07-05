from datetime import datetime

from sqlmodel import Field, SQLModel

from huisvinder.models import BaseHouse


class BaseHouseORM(SQLModel, BaseHouse, table=True):
    __tablename__ = "basehouse"
    # the ORM column stores the Literal as plain TEXT
    source: str = Field(index=True, primary_key=True)  # type: ignore[assignment]
    created_at: datetime = Field(primary_key=True, index=True)
    link: str = Field(primary_key=True, index=True)
