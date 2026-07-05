import datetime

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_json
from huisvinder.types import Sources

MAX_PRICE = 400000


def _as_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


class Immoweb(BaseSource):
    """Immoweb renders its search results from a JSON endpoint; query it
    directly instead of driving a browser."""

    name: Sources = "Immoweb"
    base_url: str = (
        "https://www.immoweb.be/en/search-results/house-and-apartment/for-sale"
        f"?countries=BE&maxPrice={MAX_PRICE}&minBedroomCount=2"
        "&postalCodes=BE-3001,3000&orderBy=relevance"
    )

    def _get_page_urls(self) -> list[str]:
        max_page = 5  # 30 results per page
        return [f"{self.base_url}&page={page_number}" for page_number in range(1, max_page + 1)]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        payload = get_json(page_url)
        results = []
        for result in payload.get("results", []):
            classified_id = result.get("id")
            property_ = result.get("property") or {}
            location = property_.get("location") or {}
            locality = location.get("locality")
            postal_code = location.get("postalCode")
            property_type = (property_.get("type") or "").lower()
            if not classified_id or not locality or not property_type:
                continue
            link = (
                f"https://www.immoweb.be/en/classified/{property_type}/for-sale"
                f"/{locality.lower()}/{postal_code}/{classified_id}"
            )

            sale = (result.get("transaction") or {}).get("sale") or {}
            price = sale.get("price")
            display_price = f"€ {price:,.0f}".replace(",", ".") if price else None

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": property_type.capitalize(),
                    "city": locality,
                    "display_price": display_price,
                    "description": _as_str(property_.get("title")),
                    "bedrooms": _as_str(property_.get("bedroomCount")),
                    "living_area": _as_str(property_.get("netHabitableSurface")),
                    "surface_ground": _as_str(property_.get("landSurface")),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
