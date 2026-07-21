import datetime

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, normalize_status
from huisvinder.types import Sources


class Immovlan(BaseSource):
    name: Sources = "Immovlan"
    base_url: str = (
        "https://immovlan.be/nl/vastgoed?transactiontypes=te-koop,in-openbare-verkoop"
        "&propertytypes=huis,appartement&towns=3052-blanden&municipals=leuven,bertem,tienen"
        "&maxprice=400000&minbedrooms=2&noindex=1"
    )

    def _get_page_urls(self) -> list[str]:
        max_page = 15
        return [
            self.base_url,
            *[
                self.base_url.replace("&noindex=1", f"&page={page_number}&noindex=1")
                for page_number in range(2, max_page + 1)
            ],
        ]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        articles = soup.find_all("article")

        results = []

        for art in articles:
            link_tag = art.find("a", href=True)
            link = str(link_tag["href"]) if link_tag else None
            if link is None:
                continue
            price_tag = art.find("strong", class_="list-item-price")
            price = price_tag.get_text(strip=True) if price_tag else None
            if not price:
                continue

            locality_tag = art.find("span", itemprop="addressLocality")
            locality = locality_tag.get_text(strip=True) if locality_tag else None

            postal_tag = art.find("span", itemprop="postalCode")
            postal_code = postal_tag.get_text(strip=True) if postal_tag else None

            ribbon = art.select_one("div.ribbon.option")
            status = normalize_status("optie" if ribbon is not None else None)

            bedrooms_tag = art.find("meta", itemprop="numberOfBedrooms")
            bedrooms = str(bedrooms_tag.get("content")) if bedrooms_tag else None

            city = " ".join(part for part in (postal_code, locality) if part) or None

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "city": city,
                    "display_price": price,
                    "status": status,
                    "bedrooms": bedrooms,
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
