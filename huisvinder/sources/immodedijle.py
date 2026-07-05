import datetime
import re
from urllib.parse import urljoin

from bs4 import Tag

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup
from huisvinder.types import Sources


class DeDijle(BaseSource):
    name: Sources = "DeDijle"
    base_url: str = "https://immodedijle.be/nl/te-koop?type=1&type=3&price-min=250000&price-max=400000"

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    @staticmethod
    def _get_features(prop: Tag) -> tuple[str | None, str | None]:
        # The feature list renders as plain text items: bedrooms, bathrooms,
        # area (icons are injected by JavaScript, absent from static HTML).
        bedrooms = living_area = None
        for li in prop.select(".estate_properties li.estate_property"):
            text = li.get_text(strip=True)
            sqm_match = re.search(r"(\d+)\s*m", text)

            if sqm_match:
                living_area = str(sqm_match.group(1))
            elif text.isdigit() and bedrooms is None:
                bedrooms = text
        return bedrooms, living_area

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        properties = soup.find_all("div", class_="col-12 col-md-6 col-lg-4")

        results = []

        for prop in properties:
            link = category = price = locality = None
            link_tag = prop.select_one(".estate-info a[href]")
            if link_tag:
                link = urljoin("https://immodedijle.be/", str(link_tag["href"]))
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

            loc_tag = prop.select_one(".estate-info-location .location")
            if loc_tag:
                locality = loc_tag.get_text(strip=True)

            bedrooms, living_area = self._get_features(prop)

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
