"""Offline tests for every scraper source, driven by trimmed HTML/JSON
fixtures captured from the live sites (tests/fixtures/)."""

from collections import Counter
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
from huisvinder.sources.homies import Homies
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
from huisvinder.utils import normalize_status, parse_price, within_budget


@dataclass
class SourceCase:
    source_class: type[BaseSource]
    module: str
    fixture: str
    cards_in_fixture: int
    expected_count: int
    n_page_urls: int
    first: dict[str, str | float | None] = field(default_factory=dict)
    statuses: dict[str, int] | None = None
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
            "price": 380000.0,
            "epc": 600,
            "address": "Zoutrootjesstraat 10, 3210 Linden",
            "city": "LINDEN",
            "category": "house",
            "bedrooms": 3,
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
            "price": 285000.0,
            "epc": 600,
            "city": "BLANKENBERGE",
            "category": "house",
            "bedrooms": 2,
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
            "price": 185000.0,
            "epc": 150,
            "city": "LEUVEN",
            "category": "other",
            "bedrooms": 1,
            "living_area": "16 m²",
        },
    ),
    SourceCase(
        BVMVastgoed,
        "huisvinder.sources.bvm_vastgoed",
        "bvm.html",
        cards_in_fixture=6,  # 2 over-budget cards are filtered client-side
        expected_count=4,
        n_page_urls=6,
        statuses={"available": 3, "option": 1},
        first={
            "display_price": "€175.000",
            "price": 175000.0,
            "epc": 50,
            "address": "Engels plein 14, 3000 Leuven",
            "city": "LEUVEN",
            "category": "other",
            "bedrooms": 1,
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
            "price": 628000.0,
            "address": "Steenweg Op Nieuwrode 212",
            "city": "ROTSELAAR",
            "category": "house",
            "bedrooms": 4,
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
        statuses={"available": 4, "option": 2},
        first={
            "display_price": "€ 699.000",
            "price": 699000.0,
            "epc": 350,
            "address": "Kampenhout, Meerlaan 56",
            "city": "KAMPENHOUT",
            "category": "house",
            "status": "available",
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
            "city": "LEUVEN",
            "category": "other",
            "bedrooms": 1,
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
            "city": "LEUVEN",
            "category": "other",
            "bedrooms": None,
            "living_area": "16 m²",
        },
    ),
    SourceCase(
        ImmoWonen,
        "huisvinder.sources.immowonen",
        "immowonen.html",
        cards_in_fixture=6,  # 3 link-less sold cards + 1 over-budget dropped
        expected_count=2,
        n_page_urls=1,
        statuses={"available": 1, "option": 1},
        first={
            "display_price": "€ 312.000",
            "city": "KERKOM",
            "category": "house",
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
            "city": "HAACHT",
            "category": "other",
            "surface_ground": "587 m²",
        },
    ),
    SourceCase(
        ImmoTerDuin,
        "huisvinder.sources.ter_duin",
        "terduin.html",
        cards_in_fixture=6,  # sold cards carry no link and are skipped
        expected_count=4,
        n_page_urls=1,
        first={
            "display_price": "€ 195.000",
            "price": 195000.0,
            "epc": 150,
            "city": "LEUVEN",
            "category": "apartment",
            "bedrooms": 1,
            "living_area": "29 m²",
        },
    ),
    SourceCase(
        Realium,
        "huisvinder.sources.realium",
        "realium.html",
        cards_in_fixture=6,  # sold-out projects are kept with status "sold"
        expected_count=6,
        n_page_urls=1,
        statuses={"available": 4, "sold": 2},
        first={
            "display_price": None,
            "city": "HOEGAARDEN",
            "category": "other",
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
            "city": "KEERBERGEN",
            "bedrooms": 3,
            "living_area": "151 m²",
        },
    ),
    SourceCase(
        ImmoRuelens,
        "huisvinder.sources.immo_ruelens",
        "ruelens.html",
        cards_in_fixture=6,  # sold/option stickers become statuses
        expected_count=6,
        n_page_urls=1,
        statuses={"available": 2, "option": 3, "sold": 1},
        first={
            "display_price": "€ 275.000",
            "city": "BUNSBEEK",
            "category": "house",
            "bedrooms": 3,
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
            "price": 283000.0,
            "epc": 250,
            "city": "AARSCHOT",
            "category": "house",
            "bedrooms": 3,
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
            "price": 89000.0,
            "address": "Rue de la Villa Romaine 39A, 6660 Houffalize",
            "city": "HOUFFALIZE",
            "category": "other",
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
            "price": 239000.0,
            "epc": 350,
            "city": "SINT-TRUIDEN",
            "category": "other",
            "bedrooms": 0,
        },
    ),
    SourceCase(
        DeImmoMakelaar,
        "huisvinder.sources.de_immo_makelaar",
        "deimmomakelaar.json",
        cards_in_fixture=3,  # the over-budget sold publication is dropped
        expected_count=2,
        n_page_urls=1,
        statuses={"available": 1, "sold": 1},
        json_based=True,
        first={
            "display_price": "€ 394.000",
            "price": 394000.0,
            "epc": 119,
            "address": "Adolphe Bastinstraat 13, 3000 Leuven",
            "city": "LEUVEN",
            "category": "other",
            "bedrooms": 3,
        },
    ),
    SourceCase(
        Immoweb,
        "huisvinder.sources.immoweb",
        "immoweb.json",
        cards_in_fixture=3,
        expected_count=3,
        n_page_urls=5,
        statuses={"available": 2, "option": 1},
        json_based=True,
        first={
            "link": "https://www.immoweb.be/en/classified/apartment/for-sale/heverlee/3001/21685566",
            "display_price": "€ 317.000",
            "price": 317000.0,
            "address": "Tiensesteenweg 222",
            "city": "HEVERLEE",
            "category": "apartment",
            "bedrooms": 2,
            "living_area": "75",
        },
    ),
    SourceCase(
        Realo,
        "huisvinder.sources.realo",
        "realo.html",
        cards_in_fixture=6,  # 2 ad/placeholder tiles without data-href are skipped
        expected_count=4,
        n_page_urls=1,
        first={
            "link": "https://www.realo.be/nl/jozef-pierrestraat-86-3010-kessel-lo/3066883?l=2137809537",
            "display_price": "€ 235.000",
            "price": 235000.0,
            "address": "Jozef pierrestraat 86, 3010 Kessel-Lo",
            "city": "KESSEL-LO",
            "category": "house",
            "bedrooms": 3,
            "living_area": "86 m²",
        },
    ),
    SourceCase(
        Homies,
        "huisvinder.sources.homies",
        "homies.html",
        cards_in_fixture=3,
        expected_count=3,
        n_page_urls=1,
        first={
            "link": "https://homies.be/panden/4408388/",
            "display_price": "€ 380.000",
            "price": 380000.0,
            "city": "LEUVEN",
            "category": "house",
            "status": "available",
            "description": "Te renoveren woning op een boogscheut centrum Leuven",
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
            "city": "TIENEN",
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
def test_listing_statuses(case):
    """Sold / under-option cards must be labelled; the rest are available."""
    houses = parse_fixture(case)
    assert len(houses) == case.expected_count <= case.cards_in_fixture
    expected = case.statuses or {"available": case.expected_count}
    assert dict(Counter(house.status for house in houses)) == expected
    for house in houses:
        if "/verkocht/" in house.link:
            assert house.status == "sold"


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


@pytest.mark.parametrize(
    ("display_price", "expected"),
    [
        ("€ 235.000", 235000.0),
        ("€175.000", 175000.0),
        ("294\u202f900 € - 349\u202f900 €", 294900.0),
        ("€ 175\xa0000", 175000.0),
        ("Vanaf € 200.000", 200000.0),
        ("Prijs op aanvraag", None),
    ],
)
def test_parse_price(display_price, expected):
    assert parse_price(display_price) == expected


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_numeric_price_is_derived(case):
    for house in parse_fixture(case):
        if house.display_price and any(ch.isdigit() for ch in house.display_price):
            assert house.price is not None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Verkocht", "sold"),
        ("recent verkocht", "sold"),
        ("Uitverkocht", "sold"),
        ("Verhuurd", "sold"),
        ("Sold", "sold"),
        ("In optie", "option"),
        ("Optie koop", "option"),
        ("under_option", "option"),
        ("Compromis in opmaak", "option"),
        ("Nieuw", "available"),
        ("new", "available"),
        ("Te koop", "available"),
        (None, "available"),
        ("", "available"),
    ],
)
def test_normalize_status(raw, expected):
    assert normalize_status(raw) == expected


def test_get_base_house_survives_broken_pages():
    """A page that raises must be skipped, not abort the whole source."""
    source = CovasImmo()
    with patch.object(CovasImmo, "_get_page_data", side_effect=RuntimeError("boom")):
        assert source.get_base_house() == []
