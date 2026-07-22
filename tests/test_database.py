import datetime
import shutil
import sqlite3
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import sqlmodel

from huisvinder import services
from huisvinder.database.crud import HuisVinderDb
from huisvinder.database.schemas import BaseHouseORM
from huisvinder.models import BaseHouse, parse_area, parse_presence

FIXTURE_DB = Path(__file__).parent / "sources" / "building.db"


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


def test_migration_harmonises_area_and_presence_columns(tmp_path: Path):
    # snapshot the raw strings first; opening the copy runs the migrations on it
    before = sqlite3.connect(FIXTURE_DB)
    try:
        columns = "source, link, living_area, surface_ground, garden, garage"
        raw = before.execute(f"SELECT {columns} FROM basehouse").fetchall()  # noqa: S608 -- literal column list
    finally:
        before.close()
    assert raw, "fixture db must contain listings"

    database = tmp_path / "building.db"
    shutil.copy(FIXTURE_DB, database)
    db = HuisVinderDb(database_path=database)

    with sqlmodel.Session(db._engine) as session:
        houses = {(h.source, h.link): h for h in session.query(BaseHouseORM).all()}
    assert len(houses) == len(raw)
    for source, link, living_area, surface_ground, garden, garage in raw:
        house = houses[source, link]
        assert isinstance(house.living_area, float | type(None))
        assert isinstance(house.surface_ground, float | type(None))
        assert isinstance(house.garden, bool | type(None))
        assert isinstance(house.garage, bool | type(None))
        # every migrated cell matches what the parser says about the raw string
        assert house.living_area == parse_area(living_area), living_area
        assert house.surface_ground == parse_area(surface_ground), surface_ground
        assert house.garden is parse_presence(garden), garden
        assert house.garage is parse_presence(garage), garage
