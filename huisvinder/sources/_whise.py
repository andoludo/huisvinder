"""Shared parser for Whise agency sites built on the grid-content template
(article.grid-content.property-grid). Several small Leuven-area agencies run
this identical Whise layout; sold listings replace the price with an
'Alle referenties bekijken' call-to-action."""

import datetime
from urllib.parse import urljoin

from bs4 import Tag

from huisvinder.config import MAX_PRICE
from huisvinder.models import BaseHouse, BaseSource
from huisvinder.utils import get_static_soup, normalize_status, within_budget

# Whise feature-list labels as rendered in each card's <i> tag; sites serve
# them in Dutch or English depending on the configured locale (the ground
# label stays the untranslated template key on both)
_FEATURE_BEDROOMS = ("Slaapkamers", "Bedrooms")
_FEATURE_LIVING = ("Leefruimte", "Living area")
_FEATURE_GROUND = ("Titles.surface_ground",)


def _feature(features: dict[str, str], labels: tuple[str, ...]) -> str | None:
    for label in labels:
        if label in features:
            return features[label]
    return None


def _features(card: Tag) -> dict[str, str]:
    features: dict[str, str] = {}
    for item in card.select(".property__features li"):
        label_tag = item.select_one("i")
        if label_tag is None:
            continue
        label = label_tag.get_text(strip=True)
        value = item.get_text(" ", strip=True).replace(label, "").strip()
        if label and value:
            features[label] = value
    return features


class WhiseGridSource(BaseSource):
    """Base source for Whise grid-content agency sites; subclasses only set
    name / base_url / _get_page_urls."""

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("article.grid-content.property-grid")

        results = []
        for card in cards:
            link_tag = card.select_one("a.property__contents")
            if link_tag is None or not link_tag.get("href"):
                continue
            link = urljoin(self.base_url, str(link_tag["href"]))
            # sold cards all point at the agency's generic references page
            if "/referenties" in link:
                continue

            # the first label in the card is the transaction state
            # (Nieuw / Te koop / In optie / Verkocht)
            labels = list(link_tag.stripped_strings)
            status = normalize_status(labels[0] if labels else None)

            price_tag = card.select_one(".price")
            price = price_tag.get_text(strip=True) if price_tag else None
            # sold listings hide the price behind a call-to-action
            if price and "referenties" in price.lower():
                price = None
            if price and not within_budget(price, MAX_PRICE):
                continue

            category_tag = card.select_one(".category")
            city_tag = card.select_one(".city")
            features = _features(card)
            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category_tag.get_text(strip=True) if category_tag else None,
                    "city": city_tag.get_text(strip=True) if city_tag else None,
                    "display_price": price,
                    "status": status,
                    "bedrooms": _feature(features, _FEATURE_BEDROOMS),
                    "living_area": _feature(features, _FEATURE_LIVING),
                    "surface_ground": _feature(features, _FEATURE_GROUND),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
