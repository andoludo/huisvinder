import datetime
import re
from typing import List
from urllib.parse import urljoin

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import temporary_web_page, scroll_to_bottom
from huisvinder.types import Sources


class DeDijle(BaseSource):
    name: Sources = "DeDijle"
    base_url: str = (
        "https://immodedijle.be/nl/te-koop?type=1&type=3&price-min=250000&price-max=400000"
    )

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        with temporary_web_page(
            page_url, headless=False, callback=scroll_to_bottom
        ) as soup:
            properties = soup.find_all("div", class_="col-12 col-md-6 col-lg-4")

            results = []

            for prop in properties:
                link = category = price = epc_label = bedrooms = bathrooms = (
                    living_area
                ) = locality = None
                link_tag = prop.select_one(".estate-info a[href]")
                if link_tag:
                    link = urljoin("https://immodedijle.be/", link_tag["href"])
                if link is None:
                    continue
                category_tag = prop.select_one(".estate-info-title h3")
                if category_tag:
                    category = category_tag.get_text(strip=True)

                price_tag = prop.select_one(".estate-price")
                if price_tag:
                    price = price_tag.get_text(strip=True)
                if price is None:
                    continue

                energy_tag = prop.select_one("img.energy-label")
                if energy_tag:
                    epc_label = energy_tag.get("alt") or energy_tag.get("src")
                loc_tag = prop.select_one(".estate-info-location .location")
                if loc_tag:
                    locality = loc_tag.get_text(strip=True)

                for li in prop.select(".estate_properties li.estate_property"):
                    text = li.get_text(strip=True)
                    svg = li.find("svg")
                    icon = svg.get("data-icon") if svg else None
                    num_match = re.search(r"\d+", text)
                    sqm_match = re.search(r"(\d+)\s*m", text)

                    if icon == "bed" and num_match:
                        bedrooms = str(num_match.group())
                    elif icon == "home" and sqm_match:
                        living_area = str(sqm_match.group(1))
                    else:
                        continue

                results.append(
                    {
                        "source": self.name,
                        "created_at": datetime.date.today(),
                        "link": link,
                        "category": category,
                        "city": locality,
                        "display_price": price,
                        "bedrooms": bedrooms,
                        "living_area": living_area,
                    }
                )
            return [BaseHouse.model_validate(r) for r in results]
