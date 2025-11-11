import datetime
from typing import List

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.services import temporary_web_page
from huisvinder.types import Sources


class Century21(BaseSource):
    name: Sources = "Century21"
    base_url: str = (
        "https://www.connect-immo.be/en/for-sale/houses,apartments/max-400000-euro"
    )

    def _get_page_urls(self) -> list[str]:
        max_page = 15
        return [
            self.base_url,
            *[
                f"{self.base_url}/page-{page_number}"
                for page_number in range(1, max_page + 1)
            ],
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        with temporary_web_page(page_url, headless=False) as soup:
            properties = soup.select("article.grid-content.property-grid")

            results = []

            for prop in properties:
                link = prop.select_one("a")["href"]  # type: ignore
                category = prop.select_one(".category").get_text(strip=True)  # type: ignore
                city = prop.select_one(".city").get_text(strip=True)  # type: ignore
                price = prop.select_one(".price").get_text(strip=True)  # type: ignore
                features = {}
                feature_items = prop.select(".property__features li")
                if price in ["Check all references"]:
                    continue

                for li in feature_items:
                    label = li.select_one("i").get_text(strip=True)  # type: ignore
                    value = li.get_text(strip=True).replace(label, "").strip()
                    features[label] = value

                results.append(
                    {
                        "source": self.name,
                        "created_at": datetime.date.today(),
                        "link": link,
                        "category": category,
                        "city": city,
                        "display_price": price,
                        "bedrooms": features.get("Bedrooms"),
                        "living_area": features.get("Living area"),
                        "surface_ground": features.get("Titles.surface_ground"),
                    }
                )
            return [BaseHouse.model_validate(r) for r in results]
