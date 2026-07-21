"""Tests for the generic detail-page enrichment, against saved detail
pages from the different site platforms (tests/fixtures/details/)."""

import datetime
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from huisvinder.details import enrich_house, harvest_pairs
from huisvinder.models import BaseHouse

DETAILS = Path(__file__).parent / "fixtures" / "details"

# (fixture, source, expected epc / address / garage / garden)
PLATFORM_CASES = [
    (
        "dedijle.html",  # Zabun template with spec tables + JSON-LD
        "DeDijle",
        {
            "epc": 137,
            "epc_is_estimated": False,
            "address": "Egenhovenweg 47 / 0301, 3001 Heverlee",
            "garden": None,
        },
    ),
    (
        "century21.html",  # Omnicasa/Elementor with English labels
        "Century21",
        {"epc": 559, "epc_is_estimated": False, "garage": "No", "garden": "Yes"},
    ),
    (
        "era.html",  # Drupal field wrappers + JSON-LD Residence
        "ERAVandendries",
        {
            "epc": 150,
            "epc_is_estimated": True,
            "address": "Karel van Lotharingenstraat 26 0101, 3000 Leuven",
        },
    ),
    (
        "immotime.html",  # WordPress/Avada spec tables
        "ImmoTime",
        {"epc": 1009, "address": "Molenstraat 38 Keerbergen"},
    ),
    (
        "marnix.html",  # Zabun/Skarabee; JSON-LD holds the agency, not the
        "MarnixVastgoed",  # property, so the 'adres' label must win
        {
            "epc": 730,
            "address": "Sint-Jorisstraat 66 Oorbeek",
            "garage": "Ja",
            "garden": "Ja",
        },
    ),
]


def make_house(**overrides) -> BaseHouse:
    values = {
        "source": "DeDijle",
        "created_at": datetime.date.today(),
        "link": "https://example.test/detail/1",
    }
    values.update(overrides)
    return BaseHouse.model_validate(values)


@pytest.mark.parametrize(
    ("fixture", "source", "expected"),
    PLATFORM_CASES,
    ids=[case[0] for case in PLATFORM_CASES],
)
def test_enrich_house_per_platform(fixture, source, expected):
    soup = BeautifulSoup((DETAILS / fixture).read_text(), "html.parser")
    house = make_house(source=source)
    enrich_house(house, soup=soup)
    for attribute, value in expected.items():
        assert getattr(house, attribute) == value, attribute


def test_enrich_house_does_not_overwrite_existing_fields():
    soup = BeautifulSoup((DETAILS / "marnix.html").read_text(), "html.parser")
    house = make_house(epc="A+", address="Kept 1, 3000 Leuven")
    enrich_house(house, soup=soup)
    assert house.epc == 0  # A+ band midpoint; already set, so not overwritten
    assert house.address == "Kept 1, 3000 Leuven"
    assert house.garage == "Ja"  # missing fields are still filled


def test_enrich_house_empty_page_leaves_fields_none():
    soup = BeautifulSoup("<html><body><p>niets</p></body></html>", "html.parser")
    house = make_house()
    enrich_house(house, soup=soup)
    assert house.epc is None
    assert house.address is None
    assert house.garage is None
    assert house.garden is None


def test_harvest_pairs_patterns():
    soup = BeautifulSoup(
        """
        <dl><dt>EPC</dt><dd>200 kWh</dd></dl>
        <table><tr><th>Garage:</th><td>Ja</td></tr></table>
        <ul><li><span>Tuin</span><span>Nee</span></li></ul>
        <div class="field"><div class="field__label">Energielabel</div> C</div>
        """,
        "html.parser",
    )
    pairs = harvest_pairs(soup)
    assert pairs["epc"] == "200 kWh"
    assert pairs["garage"] == "Ja"
    assert pairs["tuin"] == "Nee"
    assert pairs["energielabel"] == "C"
