import datetime
import re

from bs4 import Tag

from huisvinder.config import MAX_PRICE
from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, normalize_epc, normalize_status, within_budget
from huisvinder.types import Sources


def _feature_value(card: Tag, icon_class: str) -> str | None:
    icon = card.select_one(f"div.property__features span.{icon_class}")
    if icon is None or icon.parent is None:
        return None
    return icon.parent.get_text(strip=True) or None


class BVMVastgoed(BaseSource):
    name: Sources = "BVMVastgoed"
    base_url: str = "https://www.bvm-vastgoed.be/nl/te-koop"

    def _get_page_urls(self) -> list[str]:
        max_page = 6
        return [
            self.base_url,
            *[f"{self.base_url}/pagina-{page_number}" for page_number in range(2, max_page + 1)],
        ]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        # scoped to search results: bare div.property also matches <template> stubs
        cards = soup.select("div.search-results > div.property")

        results = []
        for card in cards:
            link_tag = card.select_one("a.property__title")
            if link_tag is None:
                continue
            link = str(link_tag["href"])

            price_tag = card.select_one("p.property__price")
            if price_tag is None:
                continue
            price = price_tag.get_text(strip=True)
            # the site offers no GET price filter, so filter client-side
            if not within_budget(price, MAX_PRICE):
                continue

            city = address = None
            city_tag = card.select_one("p.property__city")
            if city_tag:
                lines = [line.strip() for line in city_tag.get_text("\n").splitlines() if line.strip()]
                if lines:
                    city = lines[-1]
                    address = ", ".join(lines)

            epc = None
            epc_tag = card.select_one("span.epc")
            if epc_tag:
                modifiers = [cls for cls in epc_tag.get_attribute_list("class") if str(cls).startswith("epc--")]
                if modifiers:
                    epc = normalize_epc(modifiers[0].removeprefix("epc--"))

            sticker = card.select_one("span.property__sticker")
            status = normalize_status(sticker.get_text(strip=True) if sticker else None)

            # category is only encoded in the URL slug, e.g. /nl/huis-te-koop-in-...
            category = None
            slug_match = re.search(r"/nl/([a-z-]+?)-(?:te|optie)-koop", link)
            if slug_match:
                category = slug_match.group(1).replace("-", " ")

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "address": address,
                    "epc": epc,
                    "status": status,
                    "display_price": price,
                    "bedrooms": _feature_value(card, "icon__bedroom"),
                    "living_area": _feature_value(card, "icon__surface_livable"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
