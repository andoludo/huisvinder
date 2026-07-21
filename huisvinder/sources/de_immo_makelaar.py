import datetime
from typing import Any
from urllib.parse import urljoin

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_json, within_budget
from huisvinder.types import Sources

MAX_PRICE = 400000


def _as_str(value: Any) -> str | None:
    if value in (None, "", 0):
        return None
    return str(value)


class DeImmoMakelaar(BaseSource):
    """The site renders sold cards without prices or links, but exposes its
    Skarabee/Zabun publication feed as JSON; scrape that instead."""

    name: Sources = "DeImmoMakelaar"
    base_url: str = "https://www.deimmomakelaar.be/query/SearchPublications?transactiontype=Sale&language=NL"

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        publications = get_json(page_url).get("Publications", [])

        results = []
        for publication in publications:
            transaction = publication.get("Transaction") or {}
            if transaction.get("FlowStatus") == "Sold":
                continue

            url_path = publication.get("Url")
            if not url_path:
                continue
            link = urljoin("https://www.deimmomakelaar.be/", url_path)

            price = transaction.get("Price")
            display_price = f"€ {price:,.0f}".replace(",", ".") if price else None
            if display_price and not within_budget(display_price, MAX_PRICE):
                continue

            estate = publication.get("Estate") or {}
            address_data = estate.get("Address") or {}
            street = " ".join(
                str(part) for part in (address_data.get("Street"), address_data.get("HouseNumber")) if part
            )
            zip_city = " ".join(str(part) for part in (address_data.get("ZipCode"), address_data.get("City")) if part)
            address = ", ".join(part for part in (street, zip_city) if part) or None

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": _as_str(estate.get("Category")),
                    "city": _as_str(address_data.get("City")),
                    "address": address,
                    "epc": _as_str(estate.get("EnergyClassValue")),
                    "display_price": display_price,
                    "bedrooms": _as_str(estate.get("NumberOfBedrooms")),
                    "living_area": _as_str(estate.get("HabitableArea")),
                    "surface_ground": _as_str(estate.get("LandArea")),
                    "description": _as_str((publication.get("Flash") or {}).get("Title")),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
