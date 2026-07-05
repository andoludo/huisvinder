import datetime
from typing import Any, List, Optional

import requests

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import REQUEST_HEADERS, REQUEST_TIMEOUT
from huisvinder.types import Sources

MAX_PRICE = 400000
LEUVEN_AGENCY_ID = 33
PAGE_SIZE = 25


def _as_str(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value)


class WeInvest(BaseSource):
    """The public site is client-side rendered, but its Thor CMS exposes a
    clean JSON search API; scrape that, scoped to the Leuven office."""

    name: Sources = "WeInvest"
    base_url: str = (
        f"https://thor-cms.weinvest.app/api/properties/search"
        f"?locale=nl&transactionType=for-sale"
        f"&agencyIds%5B0%5D={LEUVEN_AGENCY_ID}"
        f"&budget%5Bmax%5D={MAX_PRICE}"
        f"&pagination%5Blimit%5D={PAGE_SIZE}"
    )

    def _get_page_urls(self) -> list[str]:
        max_page = 4
        return [
            f"{self.base_url}&pagination%5Boffset%5D={page_number * PAGE_SIZE}"
            for page_number in range(max_page)
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        response = requests.get(
            page_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        properties = response.json().get("data", [])

        results = []
        for property_ in properties:
            property_id = property_.get("id")
            city = property_.get("city") or ""
            category = property_.get("category") or ""
            if not property_id or not city or not category:
                continue
            city_slug = city.lower().replace(" ", "-")
            link = (
                f"https://weinvest.be/nl-BE/property/for-sale"
                f"/{city_slug}/{category}/{property_id}"
            )

            price = property_.get("priceAsAdvertised")
            display_price = f"€ {price:,.0f}".replace(",", ".") if price else None

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "display_price": display_price,
                    "bedrooms": _as_str(property_.get("bedroomCount")),
                    "living_area": _as_str(property_.get("livableArea")),
                    "surface_ground": _as_str(property_.get("landArea")),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
