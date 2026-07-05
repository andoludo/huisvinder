import datetime
from typing import List
from urllib.parse import urljoin

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, within_budget
from huisvinder.types import Sources

MAX_PRICE = 400000


class ImmoWonen(BaseSource):
    name: Sources = "ImmoWonen"
    base_url: str = "https://www.immowonen.be/nl/te-koop"

    def _get_page_urls(self) -> list[str]:
        # active listings only appear on page 1; later pages are all sold
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("div.property-list div.property")

        results = []
        for card in cards:
            # sold cards carry no link and show "Verkocht" instead of a price
            link_tag = card.find("a", href=True)
            if link_tag is None:
                continue
            link = urljoin("https://www.immowonen.be/", str(link_tag["href"]))

            price_tag = card.select_one(".prop-price")
            price = price_tag.get_text(strip=True) if price_tag else None
            if not price or price.lower() == "verkocht":
                continue
            # the search form is POST-only, so filter client-side
            if not within_budget(price, MAX_PRICE):
                continue

            city = category = None
            type_tag = card.select_one(".prop-type")
            if type_tag:
                text = type_tag.get_text(strip=True)
                city, _, category = (part.strip() for part in text.partition(" - "))
                city = city.title() or None
                category = category or None

            description_tag = card.select_one(".desc")
            description = (
                description_tag.get_text(strip=True) if description_tag else None
            )

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "display_price": price,
                    "description": description,
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
