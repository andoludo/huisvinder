import datetime

import pytest
from pydantic import ValidationError

from huisvinder.models import (
    BaseHouse,
    PropertyCategory,
    classify_category,
    normalise_city,
    parse_bedrooms,
    parse_epc,
    parse_epc_with_source,
)

CITY_CASES = [
    ("Heverlee", "HEVERLEE"),
    ("LEUVEN", "LEUVEN"),
    ("3000 Leuven", "LEUVEN"),
    ("3010 Kessel-Lo", "KESSEL-LO"),
    ("Leuven Heverlee", "HEVERLEE"),
    ("Herent Winksele", "WINKSELE"),
    ("Oud-Heverlee Haasrode", "HAASRODE"),
    ("Oud-Heverlee", "OUD-HEVERLEE"),
    ("Halen Zelem", "ZELEM"),
    ("Tienen Oplinter", "OPLINTER"),
    ("Leuven (Leuven)", "LEUVEN"),
    ("3000 Leuven (Leuven)", "LEUVEN"),
    ("Bunsbeek (Glabbeek)", "BUNSBEEK"),
    ("3210 Linden (Lubbeek)", "LINDEN"),
    ("3350 Orsmaal-Gussenhoven (linter)", "ORSMAAL-GUSSENHOVEN"),
    ("1000 Bruxelles", "BRUXELLES"),
    ("Scherpenheuvel-Zichem", "SCHERPENHEUVEL-ZICHEM"),
    ("  3018   Wijgmaal ", "WIJGMAAL"),
]


@pytest.mark.parametrize(("raw", "expected"), CITY_CASES)
def test_normalise_city(raw, expected):
    assert normalise_city(raw) == expected


@pytest.mark.parametrize("normalised", sorted({expected for _, expected in CITY_CASES}))
def test_normalise_city_is_idempotent(normalised):
    assert normalise_city(normalised) == normalised


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_empty_city_becomes_none(raw):
    house = make_house(city=raw)
    assert house.city is None


def test_city_is_normalised_on_the_model():
    assert make_house(city="3000 Leuven (Leuven)").city == "LEUVEN"


def test_non_string_city_is_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        make_house(city=3000)


HOUSE, APARTMENT, OTHER = PropertyCategory.HOUSE, PropertyCategory.APARTMENT, PropertyCategory.OTHER

CATEGORY_CASES = [
    # HOUSE keywords
    ("huis", HOUSE),
    ("house", HOUSE),
    ("woning", HOUSE),
    ("woonhuis", HOUSE),
    ("Eengezinswoning", HOUSE),
    ("Villa", HOUSE),
    ("Pastorijwoning", HOUSE),
    ("Bungalow", HOUSE),
    ("Herenhuis", HOUSE),
    ("Rijwoning", HOUSE),
    ("Hoeve", HOUSE),
    ("Exceptional house", HOUSE),
    # APARTMENT keywords
    ("appartement", APARTMENT),
    ("Apartment", APARTMENT),
    ("flat", APARTMENT),
    ("Studio", APARTMENT),
    ("Duplex", APARTMENT),
    ("Penthouse", APARTMENT),
    ("gelijkvloers", APARTMENT),
    ("ground floor", APARTMENT),
    ("Service Flat", APARTMENT),
    ("assistentiewoning", APARTMENT),
    # OTHER keywords
    ("grond", OTHER),
    ("Bouwgrond", OTHER),
    ("land", OTHER),
    ("Garage", OTHER),
    ("parkeerkelder", OTHER),
    ("staanplaats", OTHER),
    ("binnenstaanplaats", OTHER),
    ("Handelspand", OTHER),
    ("commercial", OTHER),
    ("office", OTHER),
    ("kantoor", OTHER),
    # deliberate exceptions from the exact-match dict
    ("Student room", OTHER),
    ("Studentenkamer", OTHER),
    ("studentenkamer", OTHER),
    ("Flat (students only)", OTHER),
    ("appartementsgebouw", OTHER),
    ("opbrengsteigendom", OTHER),
    ("Gebouw", OTHER),
    ("Gebouw voor gemengd gebruik", OTHER),
    ("flats new projects", OTHER),
    ("Residential", OTHER),
    ("Winge", OTHER),
    # ordering traps
    ("Studio Dekenstraat", APARTMENT),  # keyword stage, street name attached
    ("Woonhuis te Landen", HOUSE),  # "landen" must not match the "land" keyword
    (" - Woning", HOUSE),  # leading dash exercises the normalisation step
    ("Project Picasso", OTHER),  # prefix rule, not an enumerated value
    ("Project The Link", OTHER),
    ("Something never seen before", OTHER),  # unmatched default
]


@pytest.mark.parametrize(("raw", "expected"), CATEGORY_CASES)
def test_classify_category(raw, expected):
    assert classify_category(raw) is expected


@pytest.mark.parametrize("bucket", list(PropertyCategory))
def test_classify_category_is_idempotent(bucket):
    assert classify_category(bucket) is bucket
    assert classify_category(bucket.value) is bucket


@pytest.mark.parametrize("raw", ["", "   ", " - ", None])
def test_empty_category_becomes_none(raw):
    assert make_house(category=raw).category is None


def test_category_is_classified_on_the_model():
    assert make_house(category="Eengezinswoning").category is HOUSE


def test_non_string_category_is_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        make_house(category=7)


# (raw, expected value, expected epc_is_estimated flag)
EPC_CASES = [
    # unit notations from the sample data, all measured values
    ("269 kWh/m 2 /jaar", 269, False),
    ("763,00 kWh/(m² jaar)", 763, False),
    ("20,00 kWh/(m² jaar)", 20, False),
    ("730,00 kWh/(m² jaar)", 730, False),
    ("1009 kWh/m²", 1009, False),
    ("71 kWh/m²", 71, False),
    ("119.0", 119, False),
    ("557.0", 557, False),
    ("137 kWh/m 2 /jaar", 137, False),
    # multi-line values with a trailing band label: the number wins
    ("1413kWh/(m 2 /jaar)\n\t\t\t\t\t\t(F)", 1413, False),
    ("137kWh/(m 2 /jaar)\n\t\t\t\t\t\t(B)", 137, False),
    ("375kWh/(m 2 /jaar)\n\t\t\t\t\t\t(D)", 375, False),
    # leading label with the measurement in parentheses: the number still wins
    ("F (559 kWh/m²/year)", 559, False),
    # the 2 in the "m 2" unit spelling must not be read as the value
    ("kWh/(m 2 /jaar)", None, None),
    # bare band labels map to the band midpoint and are flagged as estimates
    ("A+", 0, True),
    ("A", 50, True),
    ("B", 150, True),
    ("C", 250, True),
    ("D", 350, True),
    ("E", 450, True),
    ("F", 600, True),
    ("f", 600, True),
    ("(F)", 600, True),
    ("D-", 350, True),  # non-standard suffix stripped
    ("E+", 450, True),
    # missing markers
    ("-", None, None),
    ("--", None, None),
    ("", None, None),
    ("n/a", None, None),
    ("nvt", None, None),
    ("Onbekend", None, None),
    # sanity bounds and junk
    ("2500 kWh/m²", None, None),
    ("G", None, None),
    ("gibberish", None, None),
]


@pytest.mark.parametrize(("raw", "expected", "estimated"), EPC_CASES)
def test_parse_epc(raw, expected, estimated):
    assert parse_epc_with_source(raw) == (expected, estimated)
    assert parse_epc(raw) == expected


def test_parse_epc_is_idempotent_on_integers():
    assert parse_epc(269) == 269
    assert parse_epc_with_source(269) == (269, False)


def test_epc_on_the_model_sets_the_estimated_flag():
    measured = make_house(epc="269 kWh/m 2 /jaar")
    assert (measured.epc, measured.epc_is_estimated) == (269, False)
    labelled = make_house(epc="B")
    assert (labelled.epc, labelled.epc_is_estimated) == (150, True)
    missing = make_house(epc=None)
    assert (missing.epc, missing.epc_is_estimated) == (None, None)


def test_epc_roundtrip_keeps_the_estimated_flag():
    # a label-derived 150 must stay flagged as an estimate after dump/validate
    house = make_house(epc="B")
    again = BaseHouse.model_validate(house.model_dump())
    assert (again.epc, again.epc_is_estimated) == (150, True)


def test_non_numeric_epc_is_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        make_house(epc=["269"])


BEDROOM_CASES = [
    ("1", 1),
    ("4", 4),
    ("0", 0),  # a studio genuinely has zero bedrooms
    ("14", 14),  # large student houses are real; the ceiling must stay >= 25
    ("None", None),  # the literal string, as scraped
    ("none", None),
    ("null", None),
    ("1 slpks.", 1),
    ("1 slpkr.", 1),
    ("2 slpkr.", 2),
    ("5 slpkr.", 5),
    ("1 slaapkamer(s)", 1),
    ("10 slaapkamer(s)", 10),
    ("1 - 2 slpkr.", 1),  # range keeps the lower bound
    ("1 – 2 slpkr.", 1),  # en dash range  # noqa: RUF001
    ("1 tot 3 slaapkamers", 1),
    ("2/3 slpkr.", 2),
    ("  3   slpkr.  ", 3),
    ("-", None),
    ("nvt", None),
    ("onbekend", None),
    ("", None),
    ("26", None),  # above the sanity ceiling
    ("gibberish", None),
]


@pytest.mark.parametrize(("raw", "expected"), BEDROOM_CASES)
def test_parse_bedrooms(raw, expected):
    assert parse_bedrooms(raw) == expected


@pytest.mark.parametrize("count", [0, 3, 14])
def test_parse_bedrooms_is_idempotent_on_integers(count):
    assert parse_bedrooms(count) == count
    assert make_house(bedrooms=count).bedrooms == count


def test_zero_bedrooms_survives_the_model():
    assert make_house(bedrooms="0").bedrooms == 0


def test_non_numeric_bedrooms_is_rejected_by_pydantic():
    with pytest.raises(ValidationError):
        make_house(bedrooms=["3"])


def make_house(**kwargs) -> BaseHouse:
    return BaseHouse(
        source="DeDijle",
        created_at=datetime.date.today(),
        link="https://example.test/1",
        **kwargs,
    )
