import logging
from abc import abstractmethod
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

from huisvinder.types import Sources

logger = logging.getLogger(__name__)


class BaseHouse(BaseModel):
    source: Sources
    created_at: datetime
    link: str
    display_price: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    bedrooms: Optional[str] = None
    living_area: Optional[str] = None
    surface_ground: Optional[str] = None


class House(BaseHouse):
    price: Optional[float] = None
    epc: Optional[str] = None
    construction_year: Optional[int] = None
    address: Optional[str] = None


class BaseSource(BaseModel):
    name: Sources
    base_url: str
    headless: bool = False

    @abstractmethod
    def _get_page_urls(self) -> List[str]: ...

    @abstractmethod
    def _get_page_data(self, page_url: str) -> List[BaseHouse]: ...

    def get_base_house(self) -> List[BaseHouse]:
        base_houses = []
        for page_url in self._get_page_urls():
            try:
                page_data = self._get_page_data(page_url)
            except Exception:
                logger.warning("Failed to scrape %s page %s", self.name, page_url)
                continue
            base_houses.extend(page_data)
        return base_houses
