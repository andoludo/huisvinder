import logging
from collections.abc import Sequence
from pathlib import Path

from huisvinder.database.crud import HuisVinderDb
from huisvinder.models import BaseHouse, BaseSource
from huisvinder.sources.bvm_vastgoed import BVMVastgoed
from huisvinder.sources.century_21 import Century21
from huisvinder.sources.covas import CovasImmo
from huisvinder.sources.de_immo_makelaar import DeImmoMakelaar
from huisvinder.sources.era_vandendries import ERAVandendries
from huisvinder.sources.immo_gve import ImmoGVE
from huisvinder.sources.immo_horst import ImmoHorst
from huisvinder.sources.immo_ruelens import ImmoRuelens
from huisvinder.sources.immo_time import ImmoTime
from huisvinder.sources.immodedijle import DeDijle
from huisvinder.sources.immolight import Immolight
from huisvinder.sources.immovlan import Immovlan
from huisvinder.sources.immoweb import Immoweb
from huisvinder.sources.immowonen import ImmoWonen
from huisvinder.sources.janstas import JanStas
from huisvinder.sources.marnix_vastgoed import MarnixVastgoed
from huisvinder.sources.realium import Realium
from huisvinder.sources.realo import Realo
from huisvinder.sources.ter_duin import ImmoTerDuin
from huisvinder.sources.we_invest import WeInvest
from huisvinder.sources.your_house import YourHouseVastgoed

logger = logging.getLogger(__name__)

SOURCES: list[type[BaseSource]] = [
    DeDijle,
    Immoweb,
    Immovlan,
    Century21,
    JanStas,
    BVMVastgoed,
    Immolight,
    ImmoHorst,
    MarnixVastgoed,
    CovasImmo,
    ImmoWonen,
    YourHouseVastgoed,
    ImmoTerDuin,
    Realium,
    ImmoTime,
    ImmoRuelens,
    DeImmoMakelaar,
    ImmoGVE,
    WeInvest,
    ERAVandendries,
    Realo,
]


def collect_houses(
    source_classes: Sequence[type[BaseSource]] | None = None,
) -> list[BaseHouse]:
    """Scrape every source and return the still-available listings."""
    houses: list[BaseHouse] = []
    for source_class in source_classes if source_classes is not None else SOURCES:
        # mypy sees the abstract base; every registered subclass is concrete
        # and defaults its own name/base_url fields
        source = source_class()  # type: ignore[call-arg]
        try:
            found = source.get_base_house()
        except Exception:
            logger.warning("Source %s failed entirely, skipping", source.name)
            continue
        logger.info("%s: %d available listings", source.name, len(found))
        houses.extend(found)
    return houses


def read_houses(database_path: Path) -> None:
    database_db = HuisVinderDb(database_path=database_path)
    database_db.add_houses(collect_houses())
