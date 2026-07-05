"""Live smoke tests hitting the real websites; excluded from the default
run (see addopts). Run explicitly with: uv run pytest -m integration --no-cov"""

import pytest

from huisvinder.sources.bvm_vastgoed import BVMVastgoed
from huisvinder.sources.century_21 import Century21
from huisvinder.sources.covas import CovasImmo
from huisvinder.sources.era_vandendries import ERAVandendries
from huisvinder.sources.immo_gve import ImmoGVE
from huisvinder.sources.immo_horst import ImmoHorst
from huisvinder.sources.immo_ruelens import ImmoRuelens
from huisvinder.sources.immo_time import ImmoTime
from huisvinder.sources.immodedijle import DeDijle
from huisvinder.sources.immolight import Immolight
from huisvinder.sources.immovlan import Immovlan
from huisvinder.sources.immoweb import Immoweb
from huisvinder.sources.janstas import JanStas
from huisvinder.sources.marnix_vastgoed import MarnixVastgoed
from huisvinder.sources.realium import Realium
from huisvinder.sources.ter_duin import ImmoTerDuin
from huisvinder.sources.we_invest import WeInvest
from huisvinder.sources.your_house import YourHouseVastgoed

# Sources expected to always expose at least one available listing.
# (ImmoWonen and DeImmoMakelaar are excluded: their in-budget stock is
# legitimately empty at times.)
LIVE_SOURCES = [
    Century21,
    DeDijle,
    JanStas,
    BVMVastgoed,
    Immolight,
    ImmoHorst,
    MarnixVastgoed,
    CovasImmo,
    YourHouseVastgoed,
    ImmoTerDuin,
    Realium,
    ImmoTime,
    ImmoRuelens,
    ImmoGVE,
    WeInvest,
    ERAVandendries,
    Immoweb,
    Immovlan,
]


@pytest.mark.integration
@pytest.mark.parametrize("source_class", LIVE_SOURCES)
def test_live_source(source_class):
    source = source_class()
    houses = []
    for url in source._get_page_urls()[:3]:
        houses.extend(source._get_page_data(url))
    assert houses
    assert all(house.link for house in houses)
