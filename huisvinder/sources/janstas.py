import datetime
from typing import List
from urllib.parse import urljoin

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup
from huisvinder.types import Sources


class JanStas(BaseSource):
    name: Sources = "JanStas"
    base_url: str = "https://immojanstas.be/nl/kopen?type=1&type=3"

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        soup = get_static_soup(page_url)
        properties = soup.find_all("div", class_="col-sm-6 col-lg-4 estate")
        results = []
        for prop in properties:
            bedrooms = living_area = None
            link_tag = prop.find("a", href=True)
            if link_tag:
                link = urljoin("https://immojanstas.be/", str(link_tag["href"]))
            else:
                continue

            title_tag = prop.find("h3", class_="title")
            locality = title_tag.text.strip() if title_tag else None

            price_tag = prop.find("p", class_="price")
            price = price_tag.text.strip() if price_tag else None
            if price is None:
                continue

            type_tag = prop.find("p", class_="type")
            category = type_tag.text.strip() if type_tag else None

            icons = prop.find_all("li", class_="icon")
            for li in icons:
                img = li.find("img")
                if not img:
                    continue

                src = img["src"]
                value = li.get_text(strip=True)

                if "bed.svg" in src:
                    bedrooms = value
                elif "house.svg" in src:  # living area icon
                    living_area = value

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
