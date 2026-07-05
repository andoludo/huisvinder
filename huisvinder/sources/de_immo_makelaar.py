import datetime
from typing import Any, List, Optional
from urllib.parse import urljoin

import requests

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import REQUEST_HEADERS, REQUEST_TIMEOUT, within_budget
from huisvinder.types import Sources

MAX_PRICE = 400000


def _as_str(value: Any) -> Optional[str]:
    if value in (None, "", 0):
        return None
    return str(value)


class DeImmoMakelaar(BaseSource):
    """The site renders sold cards without prices or links, but exposes its
    Skarabee/Zabun publication feed as JSON; scrape that instead."""

    name: Sources = "DeImmoMakelaar"
    base_url: str = (
        "https://www.deimmomakelaar.be/query/SearchPublications"
        "?transactiontype=Sale&language=NL"
    )

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        response = requests.get(
            page_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        publications = response.json().get("Publications", [])

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
            address = estate.get("Address") or {}

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": _as_str(estate.get("Category")),
                    "city": _as_str(address.get("City")),
                    "display_price": display_price,
                    "bedrooms": _as_str(estate.get("NumberOfBedrooms")),
                    "living_area": _as_str(estate.get("HabitableArea")),
                    "surface_ground": _as_str(estate.get("LandArea")),
                    "description": _as_str(
                        (publication.get("Flash") or {}).get("Title")
                    ),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
