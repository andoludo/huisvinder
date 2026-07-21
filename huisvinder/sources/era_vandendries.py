from huisvinder.models import BaseHouse, BaseSource
from huisvinder.sources._era import parse_era_page
from huisvinder.types import Sources

BROKER_ID = 6000184  # ERA Vandendries (Leuven area offices)


class ERAVandendries(BaseSource):
    name: Sources = "ERAVandendries"
    base_url: str = f"https://www.era.be/nl/te-koop?broker_id={BROKER_ID}"

    def _get_page_urls(self) -> list[str]:
        max_page = 8  # zero-based pages, 12 cards each
        return [f"{self.base_url}&page={page_number}" for page_number in range(max_page)]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        return parse_era_page(page_url, self.name)
