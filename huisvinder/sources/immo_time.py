import datetime
from typing import List, Optional

from bs4 import Tag

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup
from huisvinder.types import Sources

MAX_PRICE = 400000


def _icon_value(card: Tag, icon_class: str) -> Optional[str]:
    icon = card.select_one(f"i.fas.{icon_class}")
    if icon is None or icon.parent is None:
        return None
    value_tag = icon.parent.find("span")
    return value_tag.get_text(strip=True) if value_tag else None


class ImmoTime(BaseSource):
    name: Sources = "ImmoTime"
    base_url: str = f"https://immo-time.be/aanbod/te-koop/?max_price={MAX_PRICE}"

    def _get_page_urls(self) -> list[str]:
        # all listings render on a single page
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("ul.fusion-grid-posts-cards > li.post-card")

        results = []
        for card in cards:
            link_tag = card.select_one("a.fusion-column-anchor")
            if link_tag is None:
                continue
            link = str(link_tag["href"])

            price_tag = card.select_one("p.acf-view__price")
            if price_tag is None:
                continue
            price = price_tag.get_text(strip=True)

            city_tag = card.select_one("span.acf-view__city")
            city = (
                city_tag.get_text(strip=True).rstrip(",").strip() if city_tag else None
            )

            title_tag = card.select_one("h5.acf-view__type-description")
            description = title_tag.get_text(strip=True) if title_tag else None

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "city": city,
                    "description": description,
                    "display_price": price,
                    "bedrooms": _icon_value(card, "fa-bed"),
                    "living_area": _icon_value(card, "fa-home"),
                    "surface_ground": _icon_value(card, "fa-vector-square"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
