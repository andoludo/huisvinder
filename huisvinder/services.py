from pathlib import Path

from huisvinder.database.crud import HuisVinderDb
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
from huisvinder.sources.ter_duin import ImmoTerDuin
from huisvinder.sources.we_invest import WeInvest
from huisvinder.sources.your_house import YourHouseVastgoed


def read_houses(database_path: Path) -> None:
    database_db = HuisVinderDb(database_path=database_path)
    sources = [
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
    ]
    for source in sources:
        source_ = source()  # type: ignore[abstract]
        try:
            houses = source_.get_base_house()
        except Exception:  # noqa: S112
            continue
        if houses:
            database_db.add_houses(houses)
