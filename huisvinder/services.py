from pathlib import Path

import undetected_chromedriver as uc  # type: ignore[import-untyped]

from huisvinder.database.crud import HuisVinderDb
from huisvinder.sources.century_21 import Century21
from huisvinder.sources.immovlan import Immovlan
from huisvinder.sources.immoweb import Immoweb


def read_houses(database_path: Path):
    database_db = HuisVinderDb(database_path=database_path)
    sources = [Immoweb, Immovlan, Century21]
    for source in sources:
        source_ = source()
        try:
            houses = source_.get_base_house()
        except Exception:
            continue
        if houses:
            database_db.add_houses(houses)