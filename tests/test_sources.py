"""Offline tests for every scraper source, driven by trimmed HTML/JSON
fixtures captured from the live sites (tests/fixtures/)."""

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from conftest import (
    EMPTY_HTML,
    load_fixture_json,
    load_fixture_soup,
)
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
from huisvinder.sources.ter_duin import ImmoTerDuin
from huisvinder.sources.we_invest import WeInvest
from huisvinder.sources.your_house import YourHouseVastgoed
from huisvinder.utils import within_budget


@dataclass
class SourceCase:
    source_class: type[BaseSource]
    module: str
    fixture: str
    cards_in_fixture: int
    expected_count: int
    n_page_urls: int
    first: dict[str, str | None] = field(default_factory=dict)
    json_based: bool = False

    @property
    def id(self) -> str:
        return self.source_class.__name__


CASES = [
    SourceCase(
        Century21,
        "huisvinder.sources.century_21",
        "century21.html",
        cards_in_fixture=6,  # 3 loop stubs without price headings are skipped
        expected_count=3,
        n_page_urls=10,
        first={
            "link": "https://connect-immo.be/en/properties/3766/",
            "display_price": "€ 380.000",
            "city": "Linden",
            "category": "House",
            "bedrooms": "3",
            "living_area": "124m²",
        },
    ),
    SourceCase(
        DeDijle,
        "huisvinder.sources.immodedijle",
        "dedijle.html",
        cards_in_fixture=6,
        expected_count=6,
        n_page_urls=1,
        first={
            "display_price": "€ 285.000",
            "city": "Blankenberge",
            "category": "Eengezinswoning",
            "bedrooms": "2",
            "living_area": "210",
        },
    ),
    SourceCase(
        JanStas,
        "huisvinder.sources.janstas",
        "janstas.html",
        cards_in_fixture=6,  # 3 sold cards without link/price are skipped
        expected_count=3,
        n_page_urls=1,
        first={
            "display_price": "€ 185.000",
            "city": "Leuven",
            "category": "Studentenkamer",
            "bedrooms": "1",
            "living_area": "16 m²",
        },
    ),
    SourceCase(
        BVMVastgoed,
        "huisvinder.sources.bvm_vastgoed",
        "bvm.html",
        cards_in_fixture=6,  # 3 over-budget cards are filtered client-side
        expected_count=3,
        n_page_urls=6,
        first={
            "display_price": "€175.000",
            "city": "3000 Leuven",
            "category": "studentenkamer",
            "bedrooms": "1",
            "living_area": "30\xa0m²",
        },
    ),
    SourceCase(
        Immolight,
        "huisvinder.sources.immolight",
        "immolight.html",
        cards_in_fixture=6,  # price filtering happens server-side via the URL
        expected_count=6,
        n_page_urls=5,
        first={
            "link": "https://www.immolight.be/detail/te-koop-woning-rotselaar/7593847",
            "display_price": "€ 628.000",
            "city": "Rotselaar",
            "category": "Woning",
            "bedrooms": "4",
            "living_area": "221 m²",
        },
    ),
    SourceCase(
        ImmoHorst,
        "huisvinder.sources.immo_horst",
        "immohorst.html",
        cards_in_fixture=6,  # price filtering happens server-side via the URL
        expected_count=6,
        n_page_urls=1,
        first={
            "display_price": "€ 699.000",
            "city": "Kampenhout",
            "category": "Eengezinswoning Te koop",
            "bedrooms": None,
            "living_area": "283 m²",
        },
    ),
    SourceCase(
        MarnixVastgoed,
        "huisvinder.sources.marnix_vastgoed",
        "marnix.html",
        cards_in_fixture=6,  # price filtering happens server-side via the URL
        expected_count=6,
        n_page_urls=5,
        first={
            "display_price": "€ 175\xa0000",
            "city": "Leuven",
            "category": "studentenkamer",
            "bedrooms": "1",
            "living_area": "13 m²",
        },
    ),
    SourceCase(
        CovasImmo,
        "huisvinder.sources.covas",
        "covas.html",
        cards_in_fixture=4,  # the €1.995.000 villa is filtered client-side
        expected_count=3,
        n_page_urls=1,
        first={
            "link": "https://www.covas.be/detail?id=8931385",
            "display_price": "€ 179.000",
            "city": "Leuven",
            "category": "Studentenkamer",
            "bedrooms": None,
            "living_area": "16 m²",
        },
    ),
    SourceCase(
        ImmoWonen,
        "huisvinder.sources.immowonen",
        "immowonen.html",
        cards_in_fixture=6,  # sold + over-budget + price-on-request skipped
        expected_count=1,
        n_page_urls=1,
        first={
            "display_price": "€ 312.000",
            "city": "Kerkom",
            "category": "Huis",
        },
    ),
    SourceCase(
        YourHouseVastgoed,
        "huisvinder.sources.your_house",
        "yourhouse.html",
        cards_in_fixture=6,  # sold cards (no link/price) + over-budget skipped
        expected_count=3,
        n_page_urls=1,
        first={
            "display_price": "€ 200.000",
            "city": "Haacht",
            "category": "bouwgrond",
            "surface_ground": "587 m²",
        },
    ),
    SourceCase(
        ImmoTerDuin,
        "huisvinder.sources.ter_duin",
        "terduin.html",
        cards_in_fixture=6,  # sold cards carry no link and are skipped
        expected_count=3,
        n_page_urls=1,
        first={
            "display_price": "€ 195.000",
            "city": "Leuven",
            "category": "Studio",
            "bedrooms": "1",
            "living_area": "29 m²",
        },
    ),
    SourceCase(
        Realium,
        "huisvinder.sources.realium",
        "realium.html",
        cards_in_fixture=6,  # sold-out ("Uitverkocht") projects are skipped
        expected_count=4,
        n_page_urls=1,
        first={
            "display_price": None,
            "city": "Hoegaarden",
            "category": "Project Klein Overlaar",
        },
    ),
    SourceCase(
        ImmoTime,
        "huisvinder.sources.immo_time",
        "immotime.html",
        cards_in_fixture=6,  # price filtering happens server-side via the URL
        expected_count=6,
        n_page_urls=1,
        first={
            "link": "https://immo-time.be/home-details/6387/",
            "display_price": "€ 365.000",
            "city": "Keerbergen",
            "bedrooms": "3",
            "living_area": "151 m²",
        },
    ),
    SourceCase(
        ImmoRuelens,
        "huisvinder.sources.immo_ruelens",
        "ruelens.html",
        cards_in_fixture=6,  # cards with a sold sticker are skipped
        expected_count=5,
        n_page_urls=1,
        first={
            "display_price": "€ 275.000",
            "city": "Bunsbeek (Glabbeek)",
            "category": "Woning",
            "bedrooms": "3",
        },
    ),
    SourceCase(
        ImmoGVE,
        "huisvinder.sources.immo_gve",
        "gve.html",
        cards_in_fixture=6,  # one new-build tile without a price is skipped
        expected_count=5,
        n_page_urls=1,
        first={
            "link": "https://www.immogve.be/huis-te-koop-in-aarschot/7749315",
            "display_price": "€\xa0283.000",
            "city": "Aarschot",
            "category": "Huis",
            "bedrooms": "3",
            "living_area": "116\xa0m²",
        },
    ),
    SourceCase(
        ERAVandendries,
        "huisvinder.sources.era_vandendries",
        "era.html",
        cards_in_fixture=6,
        expected_count=6,
        n_page_urls=8,
        first={
            "display_price": "€ 89 000",
            "city": "6660 Houffalize",
            "category": "grond",
            "bedrooms": None,
        },
    ),
    SourceCase(
        WeInvest,
        "huisvinder.sources.we_invest",
        "weinvest.json",
        cards_in_fixture=5,
        expected_count=5,
        n_page_urls=4,
        json_based=True,
        first={
            "link": "https://weinvest.be/nl-BE/property/for-sale/sint-truiden/commercial/138896",
            "display_price": "€ 239.000",
            "city": "Sint-Truiden",
            "category": "commercial",
            "bedrooms": "0",
        },
    ),
    SourceCase(
        DeImmoMakelaar,
        "huisvinder.sources.de_immo_makelaar",
        "deimmomakelaar.json",
        cards_in_fixture=3,  # 2 publications with FlowStatus "Sold" are skipped
        expected_count=1,
        n_page_urls=1,
        json_based=True,
        first={
            "display_price": "€ 394.000",
            "city": "Leuven",
            "category": "Residential",
            "bedrooms": "3",
        },
    ),
    SourceCase(
        Immoweb,
        "huisvinder.sources.immoweb",
        "immoweb.json",
        cards_in_fixture=3,
        expected_count=3,
        n_page_urls=5,
        json_based=True,
        first={
            "link": "https://www.immoweb.be/en/classified/apartment/for-sale/heverlee/3001/21685566",
            "display_price": "€ 317.000",
            "city": "Heverlee",
            "category": "Apartment",
            "bedrooms": "2",
            "living_area": "75",
        },
    ),
    SourceCase(
        Immovlan,
        "huisvinder.sources.immovlan",
        "immovlan.html",
        cards_in_fixture=8,  # one teaser article without link/price is skipped
        expected_count=7,
        n_page_urls=15,
        first={
            "display_price": "294\u202f900 € - 349\u202f900 €",
            "city": "3300 Tienen",
            "bedrooms": None,
        },
    ),
]

CASE_IDS = [case.id for case in CASES]


def parse_fixture(case: SourceCase) -> list[BaseHouse]:
    source = case.source_class()
    if case.json_based:
        with patch(f"{case.module}.get_json", return_value=load_fixture_json(case.fixture)):
            return source._get_page_data("http://fixture.test/")
    with patch(f"{case.module}.get_static_soup", return_value=load_fixture_soup(case.fixture)):
        return source._get_page_data("http://fixture.test/")


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_parse_fixture(case):
    houses = parse_fixture(case)
    assert len(houses) == case.expected_count
    assert all(house.link.startswith(("http://", "https://")) for house in houses)
    first = houses[0]
    for attribute, expected in case.first.items():
        assert getattr(first, attribute) == expected, attribute


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_unavailable_listings_are_dropped(case):
    """Sold / over-budget / price-less cards in the fixture must be skipped."""
    houses = parse_fixture(case)
    assert len(houses) == case.expected_count <= case.cards_in_fixture
    for house in houses:
        assert "/verkocht/" not in house.link


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_empty_page_yields_no_houses(case):
    source = case.source_class()
    if case.json_based:
        empty: dict[str, list[object]] = {"data": [], "Publications": [], "results": []}
        with patch(f"{case.module}.get_json", return_value=empty):
            houses = source._get_page_data("http://fixture.test/")
    else:
        soup = BeautifulSoup(EMPTY_HTML, "html.parser")
        with patch(f"{case.module}.get_static_soup", return_value=soup):
            houses = source._get_page_data("http://fixture.test/")
    assert houses == []


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_page_urls(case):
    urls = case.source_class()._get_page_urls()
    assert len(urls) == case.n_page_urls
    assert len(set(urls)) == len(urls)
    assert all(url.startswith("https://") for url in urls)


def test_century21_paginates_both_property_types():
    urls = Century21()._get_page_urls()
    assert sum("oc_property_type=house" in url for url in urls) == 5
    assert sum("oc_property_type=apartment" in url for url in urls) == 5
    assert sum("/page/3/" in url for url in urls) == 2


def test_weinvest_paginates_by_offset():
    urls = WeInvest()._get_page_urls()
    offsets = [url.rsplit("=", 1)[-1] for url in urls]
    assert offsets == ["0", "25", "50", "75"]


def test_era_pages_are_zero_based():
    urls = ERAVandendries()._get_page_urls()
    assert urls[0].endswith("page=0")
    assert urls[-1].endswith("page=7")


@pytest.mark.parametrize(
    ("display_price", "expected"),
    [
        ("€ 399.000", True),
        ("€ 400.000", True),
        ("€ 400.001", False),
        ("€ 1.995.000", False),
        ("Vanaf € 225.000", True),
        ("Prijs op aanvraag", True),  # no digits: cannot be compared, keep
        ("", True),
    ],
)
def test_within_budget(display_price, expected):
    assert within_budget(display_price, 400000) is expected


def test_get_base_house_survives_broken_pages():
    """A page that raises must be skipped, not abort the whole source."""
    source = CovasImmo()
    with patch.object(CovasImmo, "_get_page_data", side_effect=RuntimeError("boom")):
        assert source.get_base_house() == []
