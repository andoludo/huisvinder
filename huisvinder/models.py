import logging
import re
import unicodedata
from abc import abstractmethod
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from huisvinder.types import Sources
from huisvinder.utils import parse_price

# Statbel suppresses cells below the disclosure threshold: the transaction count
# is published but the quartiles come back empty.
logger = logging.getLogger(__name__)

_WHITESPACE_RUN = re.compile(r"\s+")
_LEADING_POSTCODE = re.compile(r"^\d{4}\s+")
_PARENTHESISED_SUFFIX = re.compile(r"\s*\(.*\)\s*$")


def normalise_city(value: Any) -> Any:
    """Normalise a raw city name so casing/postcode/sub-municipality variants collapse.

    Rules, applied in order: (1) strip and collapse whitespace, (2) drop a
    leading four-digit Belgian postcode, (3) drop a parenthesised suffix and
    its contents (the parent municipality), (4) if a space remains keep the
    last token (the sub-municipality), (5) uppercase. Hyphens, apostrophes and
    accents are part of the name and are preserved. Empty input becomes None;
    non-string input passes through untouched so Pydantic raises its own error.
    """
    if not isinstance(value, str):
        return value
    text = _WHITESPACE_RUN.sub(" ", value).strip()
    text = _LEADING_POSTCODE.sub("", text)
    text = _PARENTHESISED_SUFFIX.sub("", text).strip()
    if " " in text:
        text = text.rsplit(" ", 1)[1]
    return text.upper() or None


CityName = Annotated[str | None, BeforeValidator(normalise_city)]


class PropertyCategory(StrEnum):
    HOUSE = "house"
    APARTMENT = "apartment"
    OTHER = "other"


_EDGE_PUNCTUATION = "-–—.,:;!?'\" "  # noqa: RUF001 -- listings really do lead with an en dash


def _category_key(value: str) -> str:
    """Normalise a raw category for matching: collapse whitespace, strip edge
    punctuation (listings often lead with a dash), casefold, drop diacritics."""
    text = _WHITESPACE_RUN.sub(" ", value).strip(_EDGE_PUNCTUATION)
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


# Stage 2: known raw values that must win over the keyword stage, e.g. whole
# investment buildings containing "appartement" or student rooms containing "flat".
_CATEGORY_EXACT: dict[str, PropertyCategory] = {
    # single rooms in a shared property, not self-contained dwellings
    "student room": PropertyCategory.OTHER,
    "studentenkamer": PropertyCategory.OTHER,
    "flat (students only)": PropertyCategory.OTHER,
    # whole multi-unit investment buildings, not a single dwelling
    "appartementsgebouw": PropertyCategory.OTHER,
    "opbrengsteigendom": PropertyCategory.OTHER,
    # bare or mixed-use building with no dwelling type stated
    "gebouw": PropertyCategory.OTHER,
    "gebouw voor gemengd gebruik": PropertyCategory.OTHER,
    # a development listing, not an individual unit
    "flats new projects": PropertyCategory.OTHER,
    # gelijkvloers / assisted-living units are self-contained dwellings
    "ground floor": PropertyCategory.APARTMENT,
    "service flat": PropertyCategory.APARTMENT,
    "residential": PropertyCategory.OTHER,  # too generic to assign
    "winge": PropertyCategory.OTHER,  # place name leaked into the category column
    "other": PropertyCategory.OTHER,  # the one bucket value with no keyword of its own
}

# Stage 3: first match wins, so OTHER patterns come first — several other-bucket
# values (studentenhuis, projectgrond, ...) contain a house/apartment substring.
# Word boundaries keep "land" from matching inside "Landen".
_CATEGORY_KEYWORDS: list[tuple[re.Pattern[str], PropertyCategory]] = [
    (re.compile(r"^project\b"), PropertyCategory.OTHER),
    (
        re.compile(
            r"\b(?:grond|bouwgrond|land|plot|garage|parkeerkelder|(?:binnen)?staanplaats"
            r"|handelspand|commercial|office|kantoor|gebouw|student\w*|opbrengst\w*|projects?)\b"
        ),
        PropertyCategory.OTHER,
    ),
    (
        re.compile(
            r"\b(?:appartement|apartment|flat|studio|duplex|penthouse|gelijkvloers"
            r"|ground floor|service flat|assistentiewoning)\b"
        ),
        PropertyCategory.APARTMENT,
    ),
    (
        re.compile(
            r"\b(?:huis|house|woning|woonhuis|eengezinswoning|villa|pastorijwoning"
            r"|bungalow|herenhuis|rijwoning|hoeve)\b"
        ),
        PropertyCategory.HOUSE,
    ),
]


def classify_category(value: Any) -> Any:
    """Collapse a raw scraped category into house / apartment / other.

    Three stages, in order: (1) normalise the text for matching, (2) exact-match
    lookup of known raw values — this runs first so deliberate exceptions beat
    the keywords (an "appartementsgebouw" is an investment building, not an
    apartment), (3) ordered keyword fallback where OTHER patterns are tested
    before APARTMENT and HOUSE because several other-bucket values contain a
    dwelling substring. Anything unmatched becomes OTHER and is logged at debug
    level. Empty input becomes None (the field is optional); non-string input
    passes through untouched so Pydantic raises its own error.
    """
    if not isinstance(value, str):
        return value
    key = _category_key(value)
    if not key:
        return None
    if (exact := _CATEGORY_EXACT.get(key)) is not None:
        return exact
    for pattern, category in _CATEGORY_KEYWORDS:
        if pattern.search(key):
            return category
    logger.debug("Unrecognised property category %r, bucketing as OTHER", value)
    return PropertyCategory.OTHER


Category = Annotated[PropertyCategory | None, BeforeValidator(classify_category)]


_EPC_MISSING = {"", "-", "--", "n/a", "nvt", "onbekend"}
# first number in the string; the lookbehinds keep the "2" in the "m 2" unit
# spelling from being read as the value when the number comes later or not at all
_EPC_NUMBER = re.compile(r"(?<!m )(?<!m)\d+(?:[.,]\d+)?")
_EPC_LABEL = re.compile(r"^\(?\s*([a-g])\s*([+-])?\s*\)?$", re.IGNORECASE)

# Midpoint of each Flemish residential EPC band (kWh/m² per year). A+ is <= 0,
# F is the open-ended > 500 band. Label-derived values are estimates with a
# 100 kWh/m² band width; epc_is_estimated keeps them distinguishable.
EPC_BAND_MIDPOINTS: dict[str, int] = {
    "A+": 0,
    "A": 50,
    "B": 150,
    "C": 250,
    "D": 350,
    "E": 450,
    "F": 600,
}
EPC_SANITY_MAX = 2000


def parse_epc_with_source(value: Any) -> tuple[Any, bool | None]:
    """Parse a raw EPC value into (kWh/m² per year, came-from-label flag).

    Stages, in order: (1) non-strings pass through untouched (numbers keep a
    False flag, anything else lets Pydantic raise); strings are whitespace-
    collapsed, (2) missing markers ('-', 'n/a', ...) become None, (3) the first
    number in the string wins and is rounded — a letter label alongside it is
    ignored because the measured value is more precise, (4) a bare letter label
    falls back to its band midpoint from EPC_BAND_MIDPOINTS ('A+' is matched
    before the generic trailing +/- strip, so 'D-' maps as 'D'), (5) anything
    else becomes None and is logged at debug level. Values outside [0, 2000]
    are parse errors and also become None.
    """
    if not isinstance(value, str):
        if isinstance(value, int | float) and not isinstance(value, bool):
            return value, False
        return value, None
    text = _WHITESPACE_RUN.sub(" ", value.replace("\xa0", " ")).strip()
    if text.casefold() in _EPC_MISSING:
        return None, None
    if number_match := _EPC_NUMBER.search(text):
        number = round(float(number_match.group().replace(",", ".")))
        if 0 <= number <= EPC_SANITY_MAX:
            return number, False
        logger.debug("EPC value %r outside the [0, %d] sanity bound, storing None", value, EPC_SANITY_MAX)
    elif (midpoint := _epc_label_midpoint(text)) is not None:
        return midpoint, True
    else:
        logger.debug("Unparseable EPC value %r, storing None", value)
    return None, None


def _epc_label_midpoint(text: str) -> int | None:
    """Band midpoint for a bare letter label; 'A+' is real and wins before the +/- strip."""
    match = _EPC_LABEL.match(text)
    if match is None:
        return None
    letter, sign = match.group(1).upper(), match.group(2) or ""
    return EPC_BAND_MIDPOINTS.get(letter + sign, EPC_BAND_MIDPOINTS.get(letter))


def parse_epc(value: Any) -> Any:
    """Value-only wrapper around parse_epc_with_source, for the field validator."""
    return parse_epc_with_source(value)[0]


EpcValue = Annotated[int | None, BeforeValidator(parse_epc)]


# "None" arrives as a literal string in this data, not as Python None
_BEDROOMS_MISSING = {"", "-", "n/a", "nvt", "onbekend", "none", "null"}
_BEDROOMS_RANGE = re.compile(r"(\d+)\s*(?:-|–|/|tot)\s*(\d+)")  # noqa: RUF001 -- ranges use a real en dash too
_BEDROOMS_NUMBER = re.compile(r"\d+")
BEDROOMS_SANITY_MAX = 25


def parse_bedrooms(value: Any) -> Any:
    """Parse a raw bedroom count into an integer.

    Stages, in order: (1) an int passes through unchanged and other non-strings
    are left for Pydantic to reject, (2) whitespace is normalised, (3) missing
    markers (including the literal strings 'None'/'null') become None, (4) a
    range ('1 - 2', '1 tot 2', '1/2') keeps its lower bound, (5) otherwise the
    first integer wins and trailing Dutch text is discarded, (6) anything else
    becomes None and is logged at debug level. Counts outside 0..25 are almost
    certainly parse errors and become None; 0 is a valid count (a studio has no
    separate bedroom) and 14-bedroom student houses are real.
    """
    if not isinstance(value, str):
        return value
    text = _WHITESPACE_RUN.sub(" ", value.replace("\xa0", " ")).strip()
    if text.casefold() in _BEDROOMS_MISSING:
        return None
    if range_match := _BEDROOMS_RANGE.search(text):
        return _bounded_bedrooms(min(int(range_match.group(1)), int(range_match.group(2))), value)
    if number_match := _BEDROOMS_NUMBER.search(text):
        return _bounded_bedrooms(int(number_match.group()), value)
    logger.debug("Unparseable bedroom count %r, storing None", value)
    return None


def _bounded_bedrooms(count: int, raw: str) -> int | None:
    if 0 <= count <= BEDROOMS_SANITY_MAX:
        return count
    logger.debug("Bedroom count %r outside the [0, %d] sanity bound, storing None", raw, BEDROOMS_SANITY_MAX)
    return None


BedroomCount = Annotated[int | None, BeforeValidator(parse_bedrooms)]


class BaseHouse(BaseModel):
    source: Sources
    created_at: datetime
    link: str
    display_price: str | None = None
    price: float | None = None
    city: CityName = None
    address: str | None = None
    category: Category = None
    description: str | None = None
    bedrooms: BedroomCount = None
    living_area: str | None = None
    surface_ground: str | None = None
    epc: EpcValue = None
    epc_is_estimated: bool | None = None
    garage: str | None = None
    garden: str | None = None
    status: str = "available"

    @model_validator(mode="before")
    @classmethod
    def _flag_estimated_epc(cls, data: Any) -> Any:
        """Record whether epc came from a band label, unless the caller already knows."""
        if isinstance(data, dict) and data.get("epc_is_estimated") is None:
            data = {**data, "epc_is_estimated": parse_epc_with_source(data.get("epc"))[1]}
        return data

    @model_validator(mode="after")
    def _derive_price(self) -> "BaseHouse":
        if self.price is None and self.display_price:
            self.price = parse_price(self.display_price)
        return self


class BaseSource(BaseModel):
    name: Sources
    base_url: str
    headless: bool = False

    @abstractmethod
    def _get_page_urls(self) -> list[str]: ...

    @abstractmethod
    def _get_page_data(self, page_url: str) -> list[BaseHouse]: ...

    def get_base_house(self) -> list[BaseHouse]:
        # dedup by link: overlapping search queries and pagination echoes
        # would otherwise repeat listings within one source run
        base_houses: dict[str, BaseHouse] = {}
        for page_url in self._get_page_urls():
            try:
                page_data = self._get_page_data(page_url)
            except Exception:
                logger.warning("Failed to scrape %s page %s", self.name, page_url)
                continue
            for house in page_data:
                base_houses.setdefault(house.link, house)
        return list(base_houses.values())


_MISSING = {"", ".", "..", "...", "-", ":", "n.b.", "NA"}


def _clean(value: Any) -> Any:
    """Normalise a raw cell: strip separators, map suppressed markers to None."""
    if not isinstance(value, str):
        return value
    text = value.strip().replace("\xa0", "").replace(" ", "")
    if text in _MISSING:
        return None
    # comma is a thousands separator in this export, never a decimal mark
    return text.replace(",", "")


Count = Annotated[int | None, BeforeValidator(_clean)]
Price = Annotated[Decimal | None, BeforeValidator(_clean)]


class Period(StrEnum):
    """Reporting period as published in the 'periode' column."""

    YEAR = "jaar"
    H1 = "S1"
    H2 = "S2"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


class PropertySalesRecord(BaseModel):
    """
    One locality/year/period row of the Statbel real estate sales table
    ('verkopen van onroerende goederen', categories per the deed of sale).

    Field names are English; aliases match the flattened Dutch column headers.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        frozen=True,
        extra="forbid",
    )

    # --- keys -------------------------------------------------------------
    nis_code: str = Field(alias="refnis", description="NIS code, kept as str to preserve leading zeros")
    locality: str = Field(alias="lokaliteit")
    year: int = Field(alias="jaar", ge=1970, le=2100)
    period: Period = Field(alias="periode")

    # --- alle huizen met 2, 3, 4 of meer gevels (excl. appartementen) ------
    all_houses_transactions: Count = Field(default=None, alias="alle_huizen__aantal_transacties")
    all_houses_median: Price = Field(default=None, alias="alle_huizen__mediaan_prijs")
    all_houses_q1: Price = Field(default=None, alias="alle_huizen__eerste_kwartiel_prijs")
    all_houses_q3: Price = Field(default=None, alias="alle_huizen__derde_kwartiel_prijs")

    # --- huizen met 2 of 3 gevels (gesloten + halfopen bebouwing) ----------
    terraced_semi_transactions: Count = Field(default=None, alias="huizen_2_of_3_gevels__aantal_transacties")
    terraced_semi_median: Price = Field(default=None, alias="huizen_2_of_3_gevels__mediaan_prijs")
    terraced_semi_q1: Price = Field(default=None, alias="huizen_2_of_3_gevels__eerste_kwartiel_prijs")
    terraced_semi_q3: Price = Field(default=None, alias="huizen_2_of_3_gevels__derde_kwartiel_prijs")

    # --- huizen met 4 of meer gevels (open bebouwing) ----------------------
    detached_transactions: Count = Field(default=None, alias="huizen_4_of_meer_gevels__aantal_transacties")
    detached_median: Price = Field(default=None, alias="huizen_4_of_meer_gevels__mediaan_prijs")
    detached_q1: Price = Field(default=None, alias="huizen_4_of_meer_gevels__eerste_kwartiel_prijs")
    detached_q3: Price = Field(default=None, alias="huizen_4_of_meer_gevels__derde_kwartiel_prijs")

    # --- appartementen -----------------------------------------------------
    apartments_transactions: Count = Field(default=None, alias="appartementen__aantal_transacties")
    apartments_median: Price = Field(default=None, alias="appartementen__mediaan_prijs")
    apartments_q1: Price = Field(default=None, alias="appartementen__eerste_kwartiel_prijs")
    apartments_q3: Price = Field(default=None, alias="appartementen__derde_kwartiel_prijs")

    @model_validator(mode="after")
    def _check_quartile_ordering(self) -> "PropertySalesRecord":
        segments = ("all_houses", "terraced_semi", "detached", "apartments")
        for segment in segments:
            q1 = getattr(self, f"{segment}_q1")
            median = getattr(self, f"{segment}_median")
            q3 = getattr(self, f"{segment}_q3")
            if None in (q1, median, q3):
                continue
            if not q1 <= median <= q3:
                raise ValueError(f"{segment}: quartiles out of order (q1={q1}, median={median}, q3={q3})")
        return self


class Simulation(BaseModel):
    budget: float = 400000
    localities: list[str] = ["BIERBEEK","HOLSBEEK","LEUVEN","OUD-HEVERLEE","LUBBEEK"]
    min_year: int = 2023
