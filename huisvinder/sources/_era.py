"""Shared parser for era.be listing cards (Drupal, article.node--property).
Both the broker-scoped and the municipality-scoped ERA queries render the
same card markup, so one parser serves both."""

import datetime
from urllib.parse import urljoin

from bs4 import Tag

from huisvinder.config import MAX_PRICE
from huisvinder.models import BaseHouse
from huisvinder.types import Sources
from huisvinder.utils import get_static_soup, normalize_status, within_budget

# the transaction segment of a detail path: /nl/te-koop/... or /en/for-sale/...
_PATH_MARKERS = ("te-koop", "for-sale")


def _card_text(card: Tag, selector: str) -> str | None:
    tag = card.select_one(selector)
    if tag is None:
        return None
    return tag.get_text(" ", strip=True) or None


def _category_from_path(link: str) -> str | None:
    # /{lang}/{marker}/{city}/{type}/{slug} -> the type segment
    parts = [part for part in link.split("/") if part]
    for marker in _PATH_MARKERS:
        if marker in parts:
            type_index = parts.index(marker) + 2
            if type_index < len(parts) - 1:
                return parts[type_index]
    return None


def parse_era_card(card: Tag, source_name: Sources) -> BaseHouse | None:
    """Parse one article.node--property card; None when it has no price or
    falls outside the budget (the SSR pages ignore the price facet)."""
    link = urljoin("https://www.era.be/", str(card["about"]))

    price = _card_text(card, ".field--price")
    if price is None or not within_budget(price, MAX_PRICE):
        return None

    address = _card_text(card, ".field--address")
    city = address.rsplit(",", 1)[-1].strip() if address else None

    return BaseHouse.model_validate(
        {
            "source": source_name,
            "created_at": datetime.date.today(),
            "link": link,
            "category": _category_from_path(link),
            "city": city,
            "address": address,
            "display_price": price,
            "status": normalize_status(_card_text(card, ".campaign-field--flag")),
            "bedrooms": _card_text(card, ".field--bedrooms"),
            "living_area": _card_text(card, ".field--habitable-space"),
            "surface_ground": _card_text(card, ".field--ground-share"),
        }
    )


def parse_era_page(page_url: str, source_name: Sources) -> list[BaseHouse]:
    soup = get_static_soup(page_url)
    houses = (parse_era_card(card, source_name) for card in soup.select("article.node--property[about]"))
    return [house for house in houses if house is not None]
