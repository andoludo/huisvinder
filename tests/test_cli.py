import csv
import datetime
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import sqlmodel
from typer.testing import CliRunner

from huisvinder import services
from huisvinder.cli import app
from huisvinder.database.crud import HuisVinderDb
from huisvinder.database.schemas import BaseHouseORM
from huisvinder.models import BaseHouse

runner = CliRunner()

HOUSE = BaseHouse(
    source="Immoweb",
    created_at=datetime.date.today(),
    link="https://example.test/1",
    display_price="€ 300.000",
    city="Leuven",
    bedrooms="3",
)


def patched_sources(stack: ExitStack, houses: list[BaseHouse]) -> None:
    for source_class in services.SOURCES:
        stack.enter_context(patch.object(source_class, "get_base_house", return_value=houses))


def test_pull_writes_csv_and_database(tmp_path: Path):
    db = tmp_path / "test.db"
    output = tmp_path / "houses.csv"
    with ExitStack() as stack:
        patched_sources(stack, [HOUSE])
        result = runner.invoke(app, ["pull", "--db", str(db), "--output", str(output)])
    assert result.exit_code == 0, result.output

    rows = list(csv.DictReader(output.open()))
    assert len(rows) == len(services.SOURCES)
    assert rows[0]["link"] == HOUSE.link
    assert rows[0]["display_price"] == HOUSE.display_price

    with sqlmodel.Session(HuisVinderDb(database_path=db)._engine) as session:
        assert len(session.query(BaseHouseORM).all()) == 1  # upserted by PK


def test_pull_json_output_and_source_selection(tmp_path: Path):
    output = tmp_path / "houses.json"
    with ExitStack() as stack:
        patched_sources(stack, [HOUSE])
        result = runner.invoke(
            app,
            ["pull", "--db", str(tmp_path / "t.db"), "--output", str(output), "--source", "immoweb", "-s", "DeDijle"],
        )
    assert result.exit_code == 0, result.output
    rows = json.loads(output.read_text())
    assert len(rows) == 2  # one per selected source
    assert rows[0]["city"] == "Leuven"


def test_pull_rejects_unknown_source(tmp_path: Path):
    result = runner.invoke(app, ["pull", "--db", str(tmp_path / "t.db"), "--source", "nope"])
    assert result.exit_code != 0
    assert "Unknown source" in result.output


def test_sources_command_lists_all():
    result = runner.invoke(app, ["sources"])
    assert result.exit_code == 0
