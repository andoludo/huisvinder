import logging
from abc import abstractmethod
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from huisvinder.types import Sources
from huisvinder.utils import parse_price

# Statbel suppresses cells below the disclosure threshold: the transaction count
# is published but the quartiles come back empty.
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
    status: str = "available"

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


_MISSING = {"", ".", "..", "...", "-", ":", "n.b.", "NA"}


def _clean(value: Any) -> Any:
    """Normalise a raw cell: strip separators, map suppressed markers to None."""
    if not isinstance(value, str):
        return value
    text = value.strip().replace("\xa0", "").replace(" ", "")
    if text in _MISSING:
        return None
    # comma is a thousands separator in this export, never a decimal mark
    return text.replace(",", "")


Count = Annotated[int | None, BeforeValidator(_clean)]
Price = Annotated[Decimal | None, BeforeValidator(_clean)]


class Period(StrEnum):
    """Reporting period as published in the 'periode' column."""

    YEAR = "jaar"
    H1 = "S1"
    H2 = "S2"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


class PropertySalesRecord(BaseModel):
    """
    One locality/year/period row of the Statbel real estate sales table
    ('verkopen van onroerende goederen', categories per the deed of sale).

    Field names are English; aliases match the flattened Dutch column headers.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        frozen=True,
        extra="forbid",
    )

    # --- keys -------------------------------------------------------------
    nis_code: str = Field(alias="refnis", description="NIS code, kept as str to preserve leading zeros")
    locality: str = Field(alias="lokaliteit")
    year: int = Field(alias="jaar", ge=1970, le=2100)
    period: Period = Field(alias="periode")

    # --- alle huizen met 2, 3, 4 of meer gevels (excl. appartementen) ------
    all_houses_transactions: Count = Field(default=None, alias="alle_huizen__aantal_transacties")
    all_houses_median: Price = Field(default=None, alias="alle_huizen__mediaan_prijs")
    all_houses_q1: Price = Field(default=None, alias="alle_huizen__eerste_kwartiel_prijs")
    all_houses_q3: Price = Field(default=None, alias="alle_huizen__derde_kwartiel_prijs")

    # --- huizen met 2 of 3 gevels (gesloten + halfopen bebouwing) ----------
    terraced_semi_transactions: Count = Field(default=None, alias="huizen_2_of_3_gevels__aantal_transacties")
    terraced_semi_median: Price = Field(default=None, alias="huizen_2_of_3_gevels__mediaan_prijs")
    terraced_semi_q1: Price = Field(default=None, alias="huizen_2_of_3_gevels__eerste_kwartiel_prijs")
    terraced_semi_q3: Price = Field(default=None, alias="huizen_2_of_3_gevels__derde_kwartiel_prijs")

    # --- huizen met 4 of meer gevels (open bebouwing) ----------------------
    detached_transactions: Count = Field(default=None, alias="huizen_4_of_meer_gevels__aantal_transacties")
    detached_median: Price = Field(default=None, alias="huizen_4_of_meer_gevels__mediaan_prijs")
    detached_q1: Price = Field(default=None, alias="huizen_4_of_meer_gevels__eerste_kwartiel_prijs")
    detached_q3: Price = Field(default=None, alias="huizen_4_of_meer_gevels__derde_kwartiel_prijs")

    # --- appartementen -----------------------------------------------------
    apartments_transactions: Count = Field(default=None, alias="appartementen__aantal_transacties")
    apartments_median: Price = Field(default=None, alias="appartementen__mediaan_prijs")
    apartments_q1: Price = Field(default=None, alias="appartementen__eerste_kwartiel_prijs")
    apartments_q3: Price = Field(default=None, alias="appartementen__derde_kwartiel_prijs")

    @model_validator(mode="after")
    def _check_quartile_ordering(self) -> "PropertySalesRecord":
        segments = ("all_houses", "terraced_semi", "detached", "apartments")
        for segment in segments:
            q1 = getattr(self, f"{segment}_q1")
            median = getattr(self, f"{segment}_median")
            q3 = getattr(self, f"{segment}_q3")
            if None in (q1, median, q3):
                continue
            if not q1 <= median <= q3:
                raise ValueError(f"{segment}: quartiles out of order (q1={q1}, median={median}, q3={q3})")
        return self
