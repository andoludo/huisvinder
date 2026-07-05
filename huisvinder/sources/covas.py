import datetime
from typing import List
from urllib.parse import urljoin

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, within_budget
from huisvinder.types import Sources

MAX_PRICE = 400000


class CovasImmo(BaseSource):
    name: Sources = "CovasImmo"
    base_url: str = "https://www.covas.be/te-koop"

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("section.products article.product")

        results = []
        for card in cards:
            link_tag = card.select_one("a.product-container")
            if link_tag is None:
                continue
            link = urljoin("https://www.covas.be/", str(link_tag["href"]))

            price_tag = card.select_one("p.book")
            if price_tag is None:
                continue
            price = price_tag.get_text(strip=True)
            # the /te-koop page ignores price query params, so filter client-side
            if not within_budget(price, MAX_PRICE):
                continue

            category = city = None
            title_tag = card.select_one(".product-block h3")
            if title_tag:
                title = title_tag.get_text(strip=True)
                category, _, city = (part.strip() for part in title.partition(" - "))
                category = category or None
                city = city or None

            bedrooms = living_area = None
            for li in card.select(".product-block li"):
                text = li.get_text(strip=True)
                if "slpks" in text:
                    bedrooms = text
                elif "m²" in text:
                    living_area = text

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
