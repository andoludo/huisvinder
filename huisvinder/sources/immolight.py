import datetime
from urllib.parse import urljoin

from bs4 import Tag

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup
from huisvinder.types import Sources

MAX_PRICE = 400000


def _icon_value(card: Tag, icon_title: str) -> str | None:
    for block in card.select("figcaption .wrap-icon-info"):
        title_tag = block.select_one("p.icon-ttl")
        if title_tag is None or title_tag.get_text(strip=True) != icon_title:
            continue
        paragraphs = block.find_all("p")
        if len(paragraphs) > 1:
            return paragraphs[-1].get_text(strip=True) or None
    return None


class Immolight(BaseSource):
    name: Sources = "Immolight"
    base_url: str = f"https://www.immolight.be/te-koop?searchon=list&sorts=Dwelling,Flat&price-to={MAX_PRICE}"

    def _get_page_urls(self) -> list[str]:
        max_page = 5
        return [f"{self.base_url}&pageindex={page_number}&pagesize=12" for page_number in range(1, max_page + 1)]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("a.pand-wrapper")

        results = []
        for card in cards:
            href = card.get("href")
            if not href:
                continue
            # strip the per-request tracking querystring so links stay stable
            link = urljoin("https://www.immolight.be/", str(href)).split("?")[0]

            price_tag = card.select_one(".boxed span")
            if price_tag is None:
                continue
            price = price_tag.get_text(strip=True)

            city = category = None
            title_tag = card.select_one(".boxed h3")
            if title_tag:
                title = title_tag.get_text(strip=True)
                city, _, category = (part.strip() for part in title.partition("-"))
                category = category or None

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "display_price": price,
                    "bedrooms": _icon_value(card, "SLAAPKAMER(S)"),
                    "living_area": _icon_value(card, "BEW. OPP."),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
