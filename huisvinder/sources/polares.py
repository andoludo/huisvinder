import datetime
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from huisvinder.config import MAX_PRICE
from huisvinder.models import BaseHouse, BaseSource
from huisvinder.types import Sources
from huisvinder.utils import normalize_status, post_json

# the user's postcode selection, in the site's own "City-postcode" tokens
POSTAL_CODES = [
    "Leuven-3000",
    "Heverlee-3001",
    "Kessel-Lo-3010",
    "Oud-Heverlee-3050",
    "Sint-Joris-Weert-3051",
    "Oud-Heverlee-3052",
    "Oud-Heverlee-3053",
    "Bierbeek-3360",
    "Korbeek-Lo-3360",
    "Oud-Heverlee-3054",
]

_SLUG = re.compile(r"[^a-z0-9]+")
_TYPE_SLUGS = {"house": "woning", "apartment": "appartement"}


def _slugify(text: str) -> str:
    return _SLUG.sub("-", text.lower()).strip("-")


def _detail_link(doc: dict[str, Any]) -> str:
    """Rebuild the site's detail URL; the server routes on the trailing id
    alone, so an imperfect slug still resolves."""
    location = doc.get("location") or {}
    city_slug = _slugify(str(location.get("city") or "onbekend"))
    type_slug = _TYPE_SLUGS.get(str(doc.get("type")), "woning")
    street = _slugify(str(location.get("street") or ""))
    number = location.get("number")
    property_slug = "-".join(str(part) for part in (f"{type_slug}-in-{street}", number) if part)
    return f"https://www.polares.eu/nl/aanbod/te-koop/{city_slug}/{property_slug}/{doc['id']}"


def _address(location: dict[str, Any]) -> str | None:
    if not location.get("street"):
        return None
    house_number = " ".join(str(part) for part in (location.get("number"), location.get("box")) if part)
    street = " ".join(part for part in (str(location["street"]), house_number) if part)
    locality = " ".join(str(part) for part in (location.get("postal_code"), location.get("city")) if part)
    return ", ".join(part for part in (street, locality) if part)


class Polares(BaseSource):
    """The public site is a Next.js app whose server-rendered pages ignore
    every filter; its /api/property/search endpoint (a JSON POST) applies
    them, and also returns the agency's sold history."""

    name: Sources = "Polares"
    base_url: str = "https://www.polares.eu/api/property/search"

    def _get_page_urls(self) -> list[str]:
        max_page = 3
        return [f"{self.base_url}?page={page_number}" for page_number in range(1, max_page + 1)]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        page_number = int(parse_qs(urlparse(page_url).query).get("page", ["1"])[0])
        response = post_json(
            self.base_url,
            {
                "negotiation": "sale",
                "type": "house",
                "postal_codes": POSTAL_CODES,
                "maxprice": str(MAX_PRICE),
                "page": page_number,
            },
        )
        data = response.get("data") or {}
        docs = data.get("docs") or [] if isinstance(data, dict) else []

        results = []
        for doc in docs:
            if not doc.get("id"):
                continue
            location = doc.get("location") or {}
            price = (doc.get("price") or {}).get("amount")
            sizes = doc.get("sizes") or {}
            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": _detail_link(doc),
                    "category": doc.get("type"),
                    "city": location.get("city"),
                    "address": _address(location),
                    "display_price": f"€ {price:,.0f}".replace(",", ".") if price else None,
                    "status": normalize_status(doc.get("status")),
                    "bedrooms": doc.get("bedrooms"),
                    "living_area": (sizes.get("liveable_area") or {}).get("size"),
                    "surface_ground": (sizes.get("plot_area") or {}).get("size"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
