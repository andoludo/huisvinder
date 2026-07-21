import datetime
import re

from bs4 import Tag

from huisvinder.config import MAX_PRICE
from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, normalize_epc
from huisvinder.types import Sources

ADDRESS_PATTERN = re.compile(r"\b(\d{4})\s+(.+)$")


def _field_value(card: Tag, field: str) -> str | None:
    value_tag = card.select_one(f".oc-property-fields__item--{field} .oc-property-fields__value")
    return value_tag.get_text(strip=True) if value_tag else None


class Century21(BaseSource):
    name: Sources = "Century21"
    base_url: str = "https://connect-immo.be/en/for-sale/"

    def _get_page_urls(self) -> list[str]:
        max_page = 5
        urls = []
        for property_type in ["house", "apartment"]:
            query = f"?oc_property_type={property_type}&oc_price_max={MAX_PRICE}"
            urls.append(f"{self.base_url}{query}")
            urls.extend(f"{self.base_url}page/{page_number}/{query}" for page_number in range(2, max_page + 1))
        return urls

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("div.e-loop-item.property")

        results = []
        for card in cards:
            link_tag = card.select_one("a[href*='/properties/']")
            if link_tag is None:
                continue
            link = str(link_tag["href"])

            price = city = address = category = epc = None
            epc_img = card.select_one("img[src*='/epc/']")
            if epc_img is not None:
                stem = str(epc_img["src"]).rsplit("/", 1)[-1].removesuffix(".png")
                epc = normalize_epc(stem.removeprefix("epc-"))
            headings = [
                heading
                for heading in card.select(".elementor-heading-title")
                if not heading.find_parent(class_="oc-status")
            ]
            for heading in headings:
                text = heading.get_text(strip=True)
                if not text:
                    continue
                if text.startswith("€"):
                    price = text
                    continue
                address_match = ADDRESS_PATTERN.search(text)
                if address_match:
                    address = text
                    city = address_match.group(2).strip().title()
                elif category is None:
                    category = text

            if price is None:
                continue

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "address": address,
                    "epc": epc,
                    "display_price": price,
                    "bedrooms": _field_value(card, "bedrooms"),
                    "living_area": _field_value(card, "surface_total"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
