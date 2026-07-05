import datetime
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import Tag

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup
from huisvinder.types import Sources

MAX_PRICE = 400000


def _icon_sibling_text(card: Tag, svg_class: str) -> Optional[str]:
    icon = card.select_one(f".shortinfo svg.{svg_class}")
    if icon is None or icon.next_sibling is None:
        return None
    return str(icon.next_sibling).strip() or None


class ImmoHorst(BaseSource):
    name: Sources = "ImmoHorst"
    base_url: str = f"https://immohorst.be/nl/te-koop?price-max={MAX_PRICE}"

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("div.estate-list_item")

        results = []
        for card in cards:
            link_tag = card.select_one("a.hypSpotlight")
            if link_tag is None:
                continue
            link = urljoin("https://immohorst.be/", str(link_tag["href"]))

            price_tag = card.select_one("span.spotlightPrice")
            if price_tag is None:
                continue
            price = price_tag.get_text(strip=True)

            city = None
            address_tag = card.select_one("span.address")
            if address_tag:
                city = address_tag.get_text(strip=True).split(",")[0].strip()

            category_tag = card.select_one(".info h3")
            category = (
                " ".join(category_tag.get_text().split()) if category_tag else None
            )

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "display_price": price,
                    "bedrooms": _icon_sibling_text(card, "fa-bed"),
                    "living_area": _icon_sibling_text(card, "icon-surface"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
