import pytest

from huisvinder.sources.bvm_vastgoed import BVMVastgoed
from huisvinder.sources.century_21 import Century21
from huisvinder.sources.covas import CovasImmo
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
from huisvinder.sources.your_house import YourHouseVastgoed

# Static-fetch sources expected to always have at least one active listing.
# (ImmoWonen and DeImmoMakelaar are excluded: their active stock within
# budget is currently empty, so an empty result is not a failure.)
STATIC_SOURCES = [
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
]


@pytest.mark.parametrize("source_class", STATIC_SOURCES)
def test_static_source(source_class) -> None:
    source = source_class()
    urls = source._get_page_urls()
    sources = []
    for url in urls[:3]:
        base_houses = source._get_page_data(url)
        sources.extend(base_houses)
    assert sources
    assert all(house.link for house in sources)


@pytest.mark.integration
def test_immoweb() -> None:
    immoweb = Immoweb()
    urls = immoweb._get_page_urls()
    sources = []
    for url in urls[:3]:
        base_houses = immoweb._get_page_data(url)
        sources.extend(base_houses)
    assert sources


@pytest.mark.integration
def test_immovlan() -> None:
    immovlan = Immovlan()
    urls = immovlan._get_page_urls()
    sources = []
    for url in urls[:3]:
        base_houses = immovlan._get_page_data(url)
        sources.extend(base_houses)
    assert sources
