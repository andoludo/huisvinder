import datetime

from bs4 import Tag

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup
from huisvinder.types import Sources

MAX_PRICE = 400000


def _card_text(card: Tag, selector: str) -> str | None:
    tag = card.select_one(selector)
    if tag is None:
        return None
    return tag.get_text(strip=True) or None


class ImmoGVE(BaseSource):
    name: Sources = "ImmoGVE"
    # price cap is encoded as a URL path segment on this Whise site
    base_url: str = f"https://www.immogve.be/te-koop/maximum-{MAX_PRICE}-euro"

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        # the card is the anchor itself; call-to-action tiles lack it
        cards = soup.select("section.properties-list li.property a.property-contents")

        results = []
        for card in cards:
            href = card.get("href")
            if not href:
                continue

            price = _card_text(card, "p.price")
            if price is None:
                continue

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": str(href),
                    "category": _card_text(card, "p.category"),
                    "city": _card_text(card, "p.city"),
                    "display_price": price,
                    "bedrooms": _card_text(card, "ul.property-features li.rooms"),
                    "living_area": _card_text(card, "ul.property-features li.area"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
