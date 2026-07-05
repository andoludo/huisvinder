import logging
from abc import abstractmethod
from datetime import datetime

from pydantic import BaseModel

from huisvinder.types import Sources

logger = logging.getLogger(__name__)


class BaseHouse(BaseModel):
    source: Sources
    created_at: datetime
    link: str
    display_price: str | None = None
    city: str | None = None
    category: str | None = None
    description: str | None = None
    bedrooms: str | None = None
    living_area: str | None = None
    surface_ground: str | None = None


class House(BaseHouse):
    price: float | None = None
    epc: str | None = None
    construction_year: int | None = None
    address: str | None = None


class BaseSource(BaseModel):
    name: Sources
    base_url: str
    headless: bool = False

    @abstractmethod
    def _get_page_urls(self) -> list[str]: ...

    @abstractmethod
    def _get_page_data(self, page_url: str) -> list[BaseHouse]: ...

    def get_base_house(self) -> list[BaseHouse]:
        base_houses = []
        for page_url in self._get_page_urls():
            try:
                page_data = self._get_page_data(page_url)
            except Exception:
                logger.warning("Failed to scrape %s page %s", self.name, page_url)
                continue
            base_houses.extend(page_data)
        return base_houses
