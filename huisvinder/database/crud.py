import logging
from functools import cached_property
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, create_engine, insert
from sqlmodel import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from huisvinder.database.schemas import BaseHouseORM, PropertySalesRecordORM
from huisvinder.database.scripts.upgrade import upgrade
from huisvinder.models import BaseHouse, PropertySalesRecord

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
        self._engine  # noqa: B018 -- touch the cached property to run migrations eagerly

    def add_houses(self, houses: list[BaseHouse]) -> None:
        if not houses:
            return
        payload = [h.model_dump() for h in houses]
        stmt = sqlite_insert(BaseHouseORM).on_conflict_do_nothing(
            index_elements=["url"],  # replace with the actual unique key
        )
        with Session(self._engine) as session:
            session.execute(stmt, payload)
            session.commit()

    def add_property_sales_records(self, records: list[PropertySalesRecord]) -> None:
        """Upsert Statbel sales records on the (nis_code, locality, year, period) primary key."""
        if not records:
            return
        with Session(self._engine) as session:
            records_ = [r.model_dump() for r in records]
            # executemany in one transaction: a single multi-VALUES statement for
            # ~37k rows x 20 columns would exceed SQLite's bind-parameter limit
            stmt = insert(PropertySalesRecordORM).prefix_with("OR REPLACE")
            for start in range(0, len(records_), BATCH_SIZE):
                session.exec(stmt, params=records_[start : start + BATCH_SIZE])
            session.commit()
