import datetime

from bs4 import Tag

from huisvinder.config import MAX_PRICE
from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, normalize_status
from huisvinder.types import Sources


def _card_text(card: Tag, selector: str) -> str | None:
    tag = card.select_one(selector)
    if tag is None:
        return None
    return tag.get_text(" ", strip=True) or None


class Homies(BaseSource):
    name: Sources = "Homies"
    base_url: str = f"https://homies.be/panden/?transaction_type=1&property_type=26&max_price={MAX_PRICE}"

    def _get_page_urls(self) -> list[str]:
        # small agency; the filtered result set fits on a single page
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("div.zabun-property-card")

        results = []
        for card in cards:
            link_tag = card.select_one("a.zabun-property-card__link")
            if link_tag is None:
                continue
            link = str(link_tag["href"])

            price = _card_text(card, ".zabun-property-card__price")
            if price is None:
                continue

            status = normalize_status(_card_text(card, ".zabun-property-card__transaction-type"))

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": _card_text(card, ".zabun-property-card__property-type"),
                    "city": _card_text(card, ".zabun-property-card__city"),
                    "display_price": price,
                    "status": status,
                    "description": _card_text(card, ".zabun-property-card__title"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
