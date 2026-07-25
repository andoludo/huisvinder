from sqlmodel import Field, SQLModel

from huisvinder.models import BaseHouse, MedianPriceRecord, PropertySalesRecord


class BaseHouseORM(SQLModel, BaseHouse, table=True):
    __tablename__ = "basehouse"
    # the ORM columns store the Literal and the category enum as plain TEXT
    source: str = Field(index=True, primary_key=True)  # type: ignore[assignment]
    link: str = Field(primary_key=True, index=True)
    category: str | None = Field(default=None)  # type: ignore[assignment]


# type ignores: the ORM columns store Period as plain TEXT and the Decimal
# prices as REAL, mirroring the BaseHouseORM pattern above.
class PropertySalesRecordORM(SQLModel, PropertySalesRecord, table=True):  # type: ignore[misc]
    nis_code: str = Field(
        alias="refnis", description="NIS code, kept as str to preserve leading zeros", index=True, primary_key=True
    )
    locality: str = Field(alias="lokaliteit", index=True, primary_key=True)
    year: int = Field(alias="jaar", ge=1970, le=2100, index=True, primary_key=True)
    period: str = Field(alias="periode", index=True, primary_key=True)  # type: ignore[assignment]

    # Statbel suppresses cells below the disclosure threshold, so every metric
    # column must accept NULL; counts and prices are independently nullable.

    # --- alle huizen met 2, 3, 4 of meer gevels (excl. appartementen) ------
    all_houses_transactions: int | None = Field(default=None, alias="alle_huizen__aantal_transacties")
    all_houses_median: float | None = Field(default=None, alias="alle_huizen__mediaan_prijs")  # type: ignore[assignment]
    all_houses_q1: float | None = Field(default=None, alias="alle_huizen__eerste_kwartiel_prijs")  # type: ignore[assignment]
    all_houses_q3: float | None = Field(default=None, alias="alle_huizen__derde_kwartiel_prijs")  # type: ignore[assignment]

    # --- huizen met 2 of 3 gevels (gesloten + halfopen bebouwing) ----------
    terraced_semi_transactions: int | None = Field(default=None, alias="huizen_2_of_3_gevels__aantal_transacties")
    terraced_semi_median: float | None = Field(default=None, alias="huizen_2_of_3_gevels__mediaan_prijs")  # type: ignore[assignment]
    terraced_semi_q1: float | None = Field(default=None, alias="huizen_2_of_3_gevels__eerste_kwartiel_prijs")  # type: ignore[assignment]
    terraced_semi_q3: float | None = Field(default=None, alias="huizen_2_of_3_gevels__derde_kwartiel_prijs")  # type: ignore[assignment]

    # --- huizen met 4 of meer gevels (open bebouwing) ----------------------
    detached_transactions: int | None = Field(default=None, alias="huizen_4_of_meer_gevels__aantal_transacties")
    detached_median: float | None = Field(default=None, alias="huizen_4_of_meer_gevels__mediaan_prijs")  # type: ignore[assignment]
    detached_q1: float | None = Field(default=None, alias="huizen_4_of_meer_gevels__eerste_kwartiel_prijs")  # type: ignore[assignment]
    detached_q3: float | None = Field(default=None, alias="huizen_4_of_meer_gevels__derde_kwartiel_prijs")  # type: ignore[assignment]

    # --- appartementen -----------------------------------------------------
    apartments_transactions: int | None = Field(default=None, alias="appartementen__aantal_transacties")
    apartments_median: float | None = Field(default=None, alias="appartementen__mediaan_prijs")  # type: ignore[assignment]
    apartments_q1: float | None = Field(default=None, alias="appartementen__eerste_kwartiel_prijs")  # type: ignore[assignment]
    apartments_q3: float | None = Field(default=None, alias="appartementen__derde_kwartiel_prijs")  # type: ignore[assignment]


# the inherited median_price column stays Decimal and maps to NUMERIC: these are
# currency values, and the natural key (nis_code, indicator, year, property_type)
# is the primary key so reloads replace rather than duplicate
class MedianPriceRecordORM(SQLModel, MedianPriceRecord, table=True):  # type: ignore[misc]
    municipality: str = Field(alias="Gemeente", index=True)
    nis_code: str = Field(
        alias="NIS-code", description="NIS code, kept as str to preserve leading zeros", index=True, primary_key=True
    )
    indicator: str = Field(alias="Indicator", primary_key=True)
    year: int = Field(alias="Jaar", ge=1900, le=2100, index=True, primary_key=True)
    property_type: str = Field(alias="Type", primary_key=True)
