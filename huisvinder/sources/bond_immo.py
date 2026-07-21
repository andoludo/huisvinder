from huisvinder.config import MAX_PRICE
from huisvinder.sources._whise import WhiseGridSource
from huisvinder.types import Sources

POSTCODES = "3360,3052,3001,3220,3010,3360,3000,3210,3360,3210,3360,3050"


class BondImmo(WhiseGridSource):
    name: Sources = "BondImmo"
    base_url: str = f"https://www.bondimmo.be/nl/te-koop/woningen/postcode-{POSTCODES}/2-kamers/max-{MAX_PRICE}-euro"

    def _get_page_urls(self) -> list[str]:
        max_page = 4
        return [
            self.base_url,
            *[f"{self.base_url}/page-{page_number}" for page_number in range(2, max_page + 1)],
        ]
