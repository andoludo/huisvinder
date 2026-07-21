import logging
from abc import abstractmethod
from datetime import datetime

from pydantic import BaseModel, model_validator

from huisvinder.types import Sources
from huisvinder.utils import parse_price

logger = logging.getLogger(__name__)


class BaseHouse(BaseModel):
    source: Sources
    created_at: datetime
    link: str
    display_price: str | None = None
    price: float | None = None
    city: str | None = None
    address: str | None = None
    category: str | None = None
    description: str | None = None
    bedrooms: str | None = None
    living_area: str | None = None
    surface_ground: str | None = None
    epc: str | None = None
    garage: str | None = None
    garden: str | None = None

    @model_validator(mode="after")
    def _derive_price(self) -> "BaseHouse":
        if self.price is None and self.display_price:
            self.price = parse_price(self.display_price)
        return self


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
