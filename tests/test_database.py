import datetime
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import sqlmodel

from huisvinder import services
from huisvinder.database.crud import HuisVinderDb
from huisvinder.database.schemas import BaseHouseORM
from huisvinder.models import BaseHouse


def make_house(link: str = "https://example.test/1") -> BaseHouse:
    return BaseHouse(
        source="DeDijle",
        created_at=datetime.date.today(),
        link=link,
        display_price="€ 300.000",
        city="Leuven",
    )


def count_rows(db: HuisVinderDb) -> int:
    with sqlmodel.Session(db._engine) as session:
        return len(session.query(BaseHouseORM).all())


def test_add_houses_upserts_on_source_date_link(tmp_path: Path):
    db = HuisVinderDb(database_path=tmp_path / "test.db")
    db.add_houses([make_house(), make_house("https://example.test/2")])
    assert count_rows(db) == 2

    # same (source, created_at, link) again: replaced, not duplicated
    db.add_houses([make_house()])
    assert count_rows(db) == 2


def test_read_houses_collects_all_sources_into_db(tmp_path: Path):
    database_path = tmp_path / "test.db"
    houses = [make_house()]
    with ExitStack() as stack:
        for name in dir(services):
            attribute = getattr(services, name)
            if isinstance(attribute, type) and hasattr(attribute, "get_base_house"):
                stack.enter_context(patch.object(attribute, "get_base_house", return_value=houses))
        services.read_houses(database_path)
    db = HuisVinderDb(database_path=database_path)
    assert count_rows(db) == 1
