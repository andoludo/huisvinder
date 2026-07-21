"""Generic detail-page enrichment.

Listing cards rarely show EPC, street address, garage or garden, but almost
every Belgian agency site renders a spec table on the listing's detail page.
This module fetches that page and harvests label/value pairs from the
markup patterns the different platforms use (definition lists, tables,
label/value list items, Drupal field wrappers) plus schema.org JSON-LD for
the address, so one implementation covers every source."""

import json
import logging
from collections.abc import Callable

from bs4 import BeautifulSoup, Tag

from huisvinder.models import BaseHouse, parse_epc_with_source
from huisvinder.utils import get_static_soup

logger = logging.getLogger(__name__)

EPC_LABELS = {
    "epc",
    "epc index",
    "epc waarde",
    "epc-waarde",
    "epc score",
    "epc label",
    "energieprestatie (epc)",
    "energieklasse",
    "energiescore",
    "energy class",
    "energielabel",
    "specifiek primair energieverbruik",
}
ADDRESS_LABELS = ["adres", "address"]
GARAGE_LABELS = [
    "garage",
    "garages",
    "garagebox",
    "parkeerplaatsen",
    "parking",
    "parkings",
    "internal parkings",
    "external parkings",
]
GARDEN_LABELS = ["tuin", "garden", "tuinoppervlakte", "tuin oppervlakte", "garden surface", "oriëntatie tuin"]

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

    for dl in soup.find_all("dl"):
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd"), strict=False):
            add(dt.get_text(" ", strip=True), dd.get_text(" ", strip=True))
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            add(cells[0].get_text(" ", strip=True), cells[1].get_text(" ", strip=True))
    for item in soup.find_all("li"):
        children = item.find_all(["span", "div", "p"], recursive=False)
        if len(children) == 2:
            add(children[0].get_text(" ", strip=True), children[1].get_text(" ", strip=True))
    _harvest_drupal_fields(soup, add)
    return pairs


def _harvest_drupal_fields(soup: BeautifulSoup, add: Callable[[str, str], None]) -> None:
    """Drupal-style field wrappers (era.be): label element + remaining text."""
    for field in soup.select("div.field"):
        label_tag = field.select_one(".field__label")
        if label_tag is None:
            continue
        label = label_tag.get_text(" ", strip=True)
        value = field.get_text(" ", strip=True).removeprefix(label)
        add(label, value)


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


def enrich_house(house: BaseHouse, soup: BeautifulSoup | Tag | None = None) -> None:
    """Fill missing epc/address/garage/garden from the listing's detail page."""
    if soup is None:
        soup = get_static_soup(house.link)
    pairs = harvest_pairs(soup)  # type: ignore[arg-type]
    if house.epc is None:
        # plain assignment skips the model's validators, so parse explicitly
        house.epc, house.epc_is_estimated = parse_epc_with_source(_lookup(pairs, EPC_LABELS))
    if house.address is None:
        house.address = _json_ld_address(soup) or _lookup(pairs, ADDRESS_LABELS)  # type: ignore[arg-type]
    if house.garage is None:
        house.garage = _lookup(pairs, GARAGE_LABELS)
    if house.garden is None:
        house.garden = _lookup(pairs, GARDEN_LABELS)


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
