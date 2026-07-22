"""Generic detail-page enrichment.

Listing cards rarely show EPC, street address, garage or garden, but almost
every Belgian agency site renders a spec table on the listing's detail page.
This module fetches that page and harvests label/value pairs from the
markup patterns the different platforms use (definition lists, tables,
label/value list items, Drupal field wrappers) plus schema.org JSON-LD for
the address, so one implementation covers every source."""

import json
import logging
import re
from collections.abc import Callable

from bs4 import BeautifulSoup, Tag

from huisvinder.models import BaseHouse, parse_epc_with_source, parse_presence
from huisvinder.utils import get_static_soup

logger = logging.getLogger(__name__)

# ordered: measured kWh/m² labels first, letter labels (band-midpoint
# estimates) as fallback
EPC_LABELS = [
    "specifiek primair energieverbruik",
    "primary energy consumption",
    "calculated specific energy consumption",
    "berekend specifiek energieverbruik",
    "energieprestatie (epc)",
    "epc index",
    "epc waarde",
    "epc-waarde",
    "epc score",
    "epc",
    "epc label",
    "energielabel",
    "energieklasse",
    "energiescore",
    "energy class",
    "energy label",
]
ADDRESS_LABELS = ["adres", "address"]
# stems matched against every harvested label ("aantal garages", "parkings
# binnen", "garagebox 1 (gelijkvloers)", "tuin aanwezig", "geschatte
# tuinoppervlakte", ...); "terras" is deliberately NOT a garden stem
GARAGE_STEMS = re.compile(r"\b(?:garage|parking|parkeer|staanplaats|autostaanplaats|carport)")
GARDEN_STEMS = re.compile(r"\b(?:tuin|garden)")

PROGRESS_EVERY = 25
# JSON-LD @types that describe the property itself (not the agency)
PROPERTY_LD_TYPES = {
    "RealEstateListing",
    "Residence",
    "House",
    "Apartment",
    "SingleFamilyResidence",
    "Product",
    "Offer",
    "Place",
}


def _clean_label(label: str) -> str:
    return label.strip().rstrip(":").strip().lower()


def harvest_pairs(soup: BeautifulSoup) -> dict[str, str]:
    """Collect spec-table label/value pairs from the common markup patterns."""
    pairs: dict[str, str] = {}

    def add(label: str, value: str) -> None:
        label, value = _clean_label(label), " ".join(value.split())
        if label and value and len(label) < 40 and len(value) < 100:
            pairs.setdefault(label, value)

    _harvest_definition_lists(soup, add)
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            add(cells[0].get_text(" ", strip=True), cells[1].get_text(" ", strip=True))
    for item in soup.find_all("li"):
        children = item.find_all(["span", "div", "p"], recursive=False)
        if len(children) == 2:
            add(children[0].get_text(" ", strip=True), children[1].get_text(" ", strip=True))
    _harvest_heading_blocks(soup, add)
    _harvest_drupal_fields(soup, add)
    return pairs


def _harvest_definition_lists(soup: BeautifulSoup, add: Callable[[str, str], None]) -> None:
    """dt/dd pairs; an empty dt continues the previous label (Whise renders
    the EPC badge and its kWh value as two consecutive rows)."""
    for dl in soup.find_all("dl"):
        last_label = ""
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd"), strict=False):
            label = dt.get_text(" ", strip=True)
            if label:
                last_label = label
            add(last_label, dd.get_text(" ", strip=True))


def _harvest_heading_blocks(soup: BeautifulSoup, add: Callable[[str, str], None]) -> None:
    """immovlan-style "<h4>label</h4> value" blocks."""
    for heading in soup.find_all("h4"):
        label = heading.get_text(" ", strip=True)
        if heading.parent is None:
            continue
        value = heading.parent.get_text(" ", strip=True).removeprefix(label)
        add(label, value)


def _harvest_drupal_fields(soup: BeautifulSoup, add: Callable[[str, str], None]) -> None:
    """Drupal-style field wrappers (era.be): label element + remaining text."""
    for field in soup.select("div.field"):
        label_tag = field.select_one(".field__label")
        if label_tag is None:
            continue
        label = label_tag.get_text(" ", strip=True)
        value = field.get_text(" ", strip=True).removeprefix(label)
        add(label, value)


_CLASSIFIED_BLOB = re.compile(r"window\.classified\s*=\s*(\{.*?\});", re.DOTALL)


def _classified_blob(soup: BeautifulSoup) -> dict[str, object]:
    """immoweb's inline window.classified JSON (its spec tables are empty in
    static HTML and only filled by JavaScript)."""
    for script in soup.find_all("script"):
        match = _CLASSIFIED_BLOB.search(script.string or "")
        if match is None:
            continue
        try:
            return dict(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    return {}


def _classified_epc(blob: dict[str, object]) -> object | None:
    certificates = (blob.get("transaction") or {}).get("certificates") or {}  # type: ignore[attr-defined]
    return certificates.get("primaryEnergyConsumptionPerSqm") or certificates.get("epcScore")


def _classified_garage(prop: dict[str, object]) -> bool | None:
    counts = [prop.get(key) for key in ("parkingCountIndoor", "parkingCountOutdoor", "parkingCountClosedBox")]
    known = [count for count in counts if isinstance(count, int | float)]
    if not known:
        return None
    return any(known)


def _classified_garden(prop: dict[str, object]) -> bool | None:
    has_garden = prop.get("hasGarden")
    if isinstance(has_garden, bool):
        return has_garden
    surface = prop.get("gardenSurface")
    if isinstance(surface, int | float):
        return surface != 0
    return None


def _json_ld_address(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for blob in data if isinstance(data, list) else [data]:
            if not isinstance(blob, dict) or blob.get("@type") not in PROPERTY_LD_TYPES:
                continue
            address = blob.get("address")
            if isinstance(address, dict) and address.get("streetAddress"):
                parts = [
                    str(address["streetAddress"]),
                    " ".join(str(part) for part in (address.get("postalCode"), address.get("addressLocality")) if part),
                ]
                return ", ".join(part for part in parts if part)
    return None


def _lookup(pairs: dict[str, str], labels: list[str] | set[str]) -> str | None:
    for label in labels:
        if label in pairs:
            return pairs[label]
    return None


def _presence_from_pairs(pairs: dict[str, str], stems: re.Pattern[str]) -> bool | None:
    """Aggregate presence over every pair whose label matches the stems: a
    site may list several slots ('parkings binnen: 1', 'parkings buiten: 0'),
    so any positive wins, then any explicit negative, else unknown."""
    found = [parse_presence(value) for label, value in pairs.items() if stems.search(label)]
    if True in found:
        return True
    if False in found:
        return False
    return None


def enrich_house(house: BaseHouse, soup: BeautifulSoup | Tag | None = None) -> None:
    """Fill missing epc/address/garage/garden from the listing's detail page."""
    if soup is None:
        soup = get_static_soup(house.link)
    pairs = harvest_pairs(soup)  # type: ignore[arg-type]
    blob = _classified_blob(soup)  # type: ignore[arg-type]
    classified_property: dict[str, object] = dict(blob.get("property") or {})  # type: ignore[call-overload]
    if house.epc is None:
        raw_epc = _lookup(pairs, EPC_LABELS)
        if raw_epc is None:
            raw_epc = _classified_epc(blob)  # type: ignore[assignment]
        # plain assignment skips the model's validators, so parse explicitly
        house.epc, house.epc_is_estimated = parse_epc_with_source(raw_epc)
    if house.address is None:
        house.address = _json_ld_address(soup) or _lookup(pairs, ADDRESS_LABELS)  # type: ignore[arg-type]
    if house.garage is None:
        # plain assignment skips the model's validators, so parse explicitly
        garage = _presence_from_pairs(pairs, GARAGE_STEMS)
        house.garage = garage if garage is not None else _classified_garage(classified_property)
    if house.garden is None:
        garden = _presence_from_pairs(pairs, GARDEN_STEMS)
        house.garden = garden if garden is not None else _classified_garden(classified_property)


def enrich_houses(houses: list[BaseHouse]) -> None:
    """Enrich every house that still misses detail fields; one request each."""
    pending = [h for h in houses if h.epc is None or h.address is None or h.garage is None or h.garden is None]
    logger.info("Enriching %d/%d listings from their detail pages", len(pending), len(houses))
    for index, house in enumerate(pending, start=1):
        try:
            enrich_house(house)
        except Exception:
            logger.warning("Could not enrich %s", house.link)
        if index % PROGRESS_EVERY == 0:
            logger.info("Enriched %d/%d", index, len(pending))
