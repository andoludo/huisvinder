import datetime
import re
from typing import List
from urllib.parse import urljoin

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, within_budget
from huisvinder.types import Sources

MAX_PRICE = 400000
CITY_PATTERN = re.compile(r"\d{4}\s+(.+)$")
AREA_PATTERN = re.compile(r"([\d.,]+\s*m²)")
SLUG_PATTERN = re.compile(r"/aanbod/\d+/([a-z-]+?)-(?:te|optie)-koop")


class YourHouseVastgoed(BaseSource):
    name: Sources = "YourHouseVastgoed"
    base_url: str = "https://yourhousevastgoed.be/nl/te-koop"

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("div.estate-list-large-item")

        results = []
        for card in cards:
            # sold cards carry no detail link and an empty price
            link_tag = card.select_one("a[href*='/aanbod/']")
            if link_tag is None:
                continue
            link = urljoin("https://yourhousevastgoed.be/", str(link_tag["href"]))

            price_tag = card.select_one("p.price")
            price = price_tag.get_text(strip=True) if price_tag else None
            if not price:
                continue
            # filters on this site are client-side React widgets only
            if not within_budget(price, MAX_PRICE):
                continue

            city = None
            address_tag = card.select_one("p.address")
            if address_tag:
                city_match = CITY_PATTERN.search(address_tag.get_text(" ", strip=True))
                if city_match:
                    city = city_match.group(1).strip()

            slug_match = SLUG_PATTERN.search(link)
            category = slug_match.group(1).replace("-", " ") if slug_match else None

            bedrooms = surface_ground = None
            for stat in card.select(".info-stats span"):
                text = stat.get_text(" ", strip=True)
                if "Slk." in text:
                    bedrooms = text.replace("Slk.", "").strip()
                    continue
                area_match = AREA_PATTERN.search(text)
                if area_match:
                    # the list card shows ground surface, not living area
                    surface_ground = area_match.group(1)

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "display_price": price,
                    "bedrooms": bedrooms,
                    "surface_ground": surface_ground,
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
