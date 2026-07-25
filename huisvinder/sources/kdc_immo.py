from huisvinder.config import MAX_PRICE
from huisvinder.sources._whise import WhiseGridSource
from huisvinder.types import Sources


class KDCImmo(WhiseGridSource):
    name: Sources = "KDCImmo"
    base_url: str = f"https://www.kdcimmo.be/en/for-sale/houses/2-bedrooms/max-{MAX_PRICE}-euro"

    def _get_page_urls(self) -> list[str]:
        # the full stock fits on one page (page-2 renders an empty grid)
        return [self.base_url]
