import datetime
import re
from urllib.parse import urljoin

from bs4 import Tag

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup
from huisvinder.types import Sources

MAX_PRICE = 400000
AREA_PATTERN = re.compile(r"(\d+)\s*m")


def _card_text(card: Tag, selector: str) -> str | None:
    tag = card.select_one(selector)
    if tag is None:
        return None
    return tag.get_text(" ", strip=True) or None


class Realo(BaseSource):
    name: Sources = "Realo"
    # mobile=true serves the server-rendered variant of the search results
    base_url: str = f"https://www.realo.be/nl/search/huis/te-koop/leuven?priceMax={MAX_PRICE}&bedroomsMin=2&mobile=true"

    def _get_page_urls(self) -> list[str]:
        # the filtered result set fits on a single page
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("div.component-estate-grid-item")

        results = []
        for card in cards:
            # ad/placeholder tiles carry no data-href
            href = str(card.get("data-href") or "").strip()
            if not href:
                continue
            link = urljoin("https://www.realo.be/", href)

            price = _card_text(card, ".label-price")
            if price is None:
                continue

            city = None
            address = _card_text(card, "div.address")
            if address:
                city = address.split(",")[-1].strip() or None

            # "Huis te koop" -> "Huis"
            category = _card_text(card, "span.type")
            if category:
                category = category.split(" te ")[0].strip() or None

            bedrooms = living_area = None
            beds_text = _card_text(card, ".details span.beds")
            if beds_text:
                digits = re.sub(r"\D", "", beds_text)
                bedrooms = digits or None
            area_text = _card_text(card, ".details span.area")
            if area_text:
                area_match = AREA_PATTERN.search(area_text)
                if area_match:
                    living_area = f"{area_match.group(1)} m²"

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "address": address,
                    "display_price": price,
                    "bedrooms": bedrooms,
                    "living_area": living_area,
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
