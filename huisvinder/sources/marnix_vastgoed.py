import datetime
from urllib.parse import urljoin

from bs4 import Tag

from huisvinder.config import MAX_PRICE
from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup
from huisvinder.types import Sources


def _feature_value(card: Tag, feature: str) -> str | None:
    value_tag = card.select_one(f"dl.feature__item--{feature} dd")
    return value_tag.get_text(strip=True) if value_tag else None


class MarnixVastgoed(BaseSource):
    name: Sources = "MarnixVastgoed"
    base_url: str = (
        f"https://www.marnixvastgoed.be/te-koop?dosearch=True&searchpage=ForSale"
        f"&transactiontype=Sale&pagesize=12&sorts%5B%5D=Dwelling&sorts%5B%5D=Flat"
        f"&price-to={MAX_PRICE}"
    )

    def _get_page_urls(self) -> list[str]:
        max_page = 5
        return [f"{self.base_url}&pageindex={page_number}" for page_number in range(1, max_page + 1)]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("article.card--property")

        results = []
        for card in cards:
            link_tag = card.select_one("a.card__image__link")
            if link_tag is None:
                continue
            # strip the per-request tracking querystring so links stay stable
            link = urljoin("https://www.marnixvastgoed.be/", str(link_tag["href"])).split("?")[0]

            price_tag = card.select_one(".card-header h4.card__subtitle")
            if price_tag is None:
                continue
            price = price_tag.get_text(strip=True)

            city_tag = card.select_one("h3.card-title span")
            city = city_tag.get_text(strip=True) if city_tag else None

            address_tag = card.select_one(".card-body__address address")
            address = address_tag.get_text(" ", strip=True) if address_tag else None

            # link title reads "Te koop studentenkamer - Leuven"
            category = None
            title = str(link_tag.get("title") or "")
            if title.lower().startswith("te koop"):
                category = title[len("te koop") :].split(" - ", maxsplit=1)[0].strip() or None

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "address": address,
                    "display_price": price,
                    "bedrooms": _feature_value(card, "bed"),
                    "living_area": _feature_value(card, "habitable"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
