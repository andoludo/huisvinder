import datetime
from typing import List
from urllib.parse import urljoin

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, within_budget
from huisvinder.types import Sources

MAX_PRICE = 400000


class ImmoTerDuin(BaseSource):
    name: Sources = "ImmoTerDuin"
    base_url: str = "https://immoterduin.be/nl/te-koop"

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("div.estate-list-item")

        results = []
        for card in cards:
            # sold cards carry no detail link
            link_tag = card.select_one("a[href*='/aanbod/']")
            if link_tag is None:
                continue
            link = urljoin("https://immoterduin.be/", str(link_tag["href"]))

            price_tag = card.select_one("p.price")
            price = price_tag.get_text(strip=True) if price_tag else None
            if not price:
                continue
            # filters on this site are client-side React widgets only
            if not within_budget(price, MAX_PRICE):
                continue

            category = city = None
            title_tag = card.select_one("h2.title")
            if title_tag:
                title = title_tag.get_text(" ", strip=True)
                category, _, city = (part.strip() for part in title.partition(" in "))
                category = category or None
                city = city or None

            # icon labels carry no semantic classes; bedrooms is the first
            # bare number, the living area is the label carrying m²
            bedrooms = living_area = None
            for label_tag in card.select(".estate-icons .icon .label"):
                text = label_tag.get_text(strip=True)
                if "m²" in text:
                    living_area = text
                elif text.isdigit() and bedrooms is None:
                    bedrooms = text

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "display_price": price,
                    "bedrooms": bedrooms,
                    "living_area": living_area,
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
