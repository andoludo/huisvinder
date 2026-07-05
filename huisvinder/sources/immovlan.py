import datetime

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import temporary_web_page, find_cookie_banner
from huisvinder.types import Sources

xpath = "/html/body/div[1]/div/div/div/div/div/div[2]/button[2]"


class Immovlan(BaseSource):
    name: Sources = "Immovlan"
    base_url: str = "https://immovlan.be/nl/vastgoed?transactiontypes=te-koop,in-openbare-verkoop&propertytypes=huis,appartement&towns=3052-blanden&municipals=leuven,bertem,tienen&maxprice=400000&minbedrooms=2&noindex=1"

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
        with temporary_web_page(
            page_url,
            headless=False,
            callback=lambda driver: find_cookie_banner(driver, xpath),
        ) as soup:
            articles = soup.find_all("article")

            results = []

            for art in articles:
                link_tag = art.find("a", href=True)
                link = link_tag["href"] if link_tag else None
                if link is None:
                    continue
                price_tag = art.find("strong", class_="list-item-price")
                price = price_tag.get_text(strip=True) if price_tag else None

                # --- LOCALITY (addressLocality) ---
                locality_tag = art.find("span", itemprop="addressLocality")
                locality = locality_tag.get_text(strip=True) if locality_tag else None

                # --- POSTAL CODE ---
                postal_tag = art.find("span", itemprop="postalCode")
                postal_code = postal_tag.get_text(strip=True) if postal_tag else None

                # --- BEDROOMS ---
                bedrooms_tag = art.find("meta", itemprop="numberOfBedrooms")
                bedrooms = bedrooms_tag.get("content") if bedrooms_tag else None

                results.append(
                    {
                        "source": self.name,
                        "created_at": datetime.date.today(),
                        "link": link,
                        "city": f"{postal_code} {locality}",
                        "display_price": price,
                        "bedrooms": bedrooms,
                    }
                )
            return [BaseHouse.model_validate(r) for r in results]
