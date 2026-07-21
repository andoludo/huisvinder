import datetime
from urllib.parse import urljoin

from bs4 import Tag

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, within_budget
from huisvinder.types import Sources

MAX_PRICE = 400000
BROKER_ID = 6000184  # ERA Vandendries (Leuven area offices)


def _card_text(card: Tag, selector: str) -> str | None:
    tag = card.select_one(selector)
    if tag is None:
        return None
    return tag.get_text(" ", strip=True) or None


class ERAVandendries(BaseSource):
    name: Sources = "ERAVandendries"
    base_url: str = f"https://www.era.be/nl/te-koop?broker_id={BROKER_ID}"

    def _get_page_urls(self) -> list[str]:
        max_page = 8  # zero-based pages, 12 cards each
        return [f"{self.base_url}&page={page_number}" for page_number in range(max_page)]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("article.node--property[about]")

        results = []
        for card in cards:
            link = urljoin("https://www.era.be/", str(card["about"]))

            price = _card_text(card, ".field--price")
            if price is None:
                continue
            # the server-rendered page ignores price facets, filter client-side
            if not within_budget(price, MAX_PRICE):
                continue

            city = None
            address = _card_text(card, ".field--address")
            if address:
                city = address.rsplit(",", 1)[-1].strip()

            # category only appears in the URL: /nl/te-koop/{city}/{type}/{slug}
            category = None
            path_parts = [part for part in link.split("/") if part]
            if "te-koop" in path_parts:
                type_index = path_parts.index("te-koop") + 2
                if type_index < len(path_parts) - 1:
                    category = path_parts[type_index]

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "address": address,
                    "display_price": price,
                    "bedrooms": _card_text(card, ".field--bedrooms"),
                    "living_area": _card_text(card, ".field--habitable-space"),
                    "surface_ground": _card_text(card, ".field--ground-share"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
