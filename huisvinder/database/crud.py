import logging
from functools import cached_property
from pathlib import Path
from typing import Any, List

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, create_engine, insert
from sqlmodel import Session

from huisvinder.database.schemas import BaseHouseORM
from huisvinder.database.scripts.upgrade import upgrade
from huisvinder.models import House, BaseHouse

logger = logging.getLogger(__name__)

BATCH_SIZE = 5000


class HuisVinderDb(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    database_path: Path


    @cached_property
    def _engine(self) -> Engine:
        database_url = f"sqlite:///{Path(self.database_path)}"
        upgrade(database_url)
        engine = create_engine(database_url)
        return engine

    def model_post_init(self, __context: Any) -> None:
        self._engine  # noqa: B018

    def add_houses(self, houses: List[BaseHouse]) -> None:
        with Session(self._engine) as session:
            houses_ = [h.model_dump() for h in houses]
            stmt = (
                insert(BaseHouseORM).prefix_with("OR REPLACE").values(houses_)
            )
            session.exec(stmt)  # type: ignore
            session.commit()
