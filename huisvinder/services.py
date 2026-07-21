import logging
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from pydantic import ValidationError

from huisvinder.database.crud import HuisVinderDb
from huisvinder.details import enrich_houses
from huisvinder.models import BaseHouse, BaseSource, PropertySalesRecord
from huisvinder.sources.bvm_vastgoed import BVMVastgoed
from huisvinder.sources.century_21 import Century21
from huisvinder.sources.covas import CovasImmo
from huisvinder.sources.de_immo_makelaar import DeImmoMakelaar
from huisvinder.sources.era_vandendries import ERAVandendries
from huisvinder.sources.immo_gve import ImmoGVE
from huisvinder.sources.immo_horst import ImmoHorst
from huisvinder.sources.immo_ruelens import ImmoRuelens
from huisvinder.sources.immo_time import ImmoTime
from huisvinder.sources.immodedijle import DeDijle
from huisvinder.sources.immolight import Immolight
from huisvinder.sources.immovlan import Immovlan
from huisvinder.sources.immoweb import Immoweb
from huisvinder.sources.immowonen import ImmoWonen
from huisvinder.sources.janstas import JanStas
from huisvinder.sources.marnix_vastgoed import MarnixVastgoed
from huisvinder.sources.realium import Realium
from huisvinder.sources.realo import Realo
from huisvinder.sources.ter_duin import ImmoTerDuin
from huisvinder.sources.we_invest import WeInvest
from huisvinder.sources.your_house import YourHouseVastgoed

logger = logging.getLogger(__name__)

SOURCES: list[type[BaseSource]] = [
    DeDijle,
    Immoweb,
    Immovlan,
    Century21,
    JanStas,
    BVMVastgoed,
    Immolight,
    ImmoHorst,
    MarnixVastgoed,
    CovasImmo,
    ImmoWonen,
    YourHouseVastgoed,
    ImmoTerDuin,
    Realium,
    ImmoTime,
    ImmoRuelens,
    DeImmoMakelaar,
    ImmoGVE,
    WeInvest,
    ERAVandendries,
    Realo,
]


def collect_houses(
    source_classes: Sequence[type[BaseSource]] | None = None,
    with_details: bool = False,
) -> list[BaseHouse]:
    """Scrape every source and return the still-available listings.

    With with_details, each listing's detail page is also fetched to fill
    missing epc/address/garage/garden fields (one extra request per listing)."""
    houses: list[BaseHouse] = []
    for source_class in source_classes if source_classes is not None else SOURCES:
        # mypy sees the abstract base; every registered subclass is concrete
        # and defaults its own name/base_url fields
        source = source_class()  # type: ignore[call-arg]
        try:
            found = source.get_base_house()
        except Exception:
            logger.warning("Source %s failed entirely, skipping", source.name)
            continue
        logger.info("%s: %d available listings", source.name, len(found))
        houses.extend(found)
    if with_details:
        enrich_houses(houses)
    return houses


def read_houses(database_path: Path) -> None:
    database_db = HuisVinderDb(database_path=database_path)
    database_db.add_houses(collect_houses())


STATISTICS_XLSX = Path(__file__).parent / "statistics" / "NL_immo_statbel_kwartaal_per_gemeente.xlsx"

_KEY_COLUMNS = {"refnis", "lokaliteit", "jaar", "periode"}

# banner text (lowercased prefix) -> segment slug used in the flattened header
_SEGMENT_PREFIXES = [
    ("alle huizen", "alle_huizen"),
    ("huizen met 2 of 3 gevels", "huizen_2_of_3_gevels"),
    ("huizen met 4 of meer gevels", "huizen_4_of_meer_gevels"),
    ("appartementen", "appartementen"),
]

# metric header (lowercased) -> metric slug used in the flattened header
_METRIC_SLUGS = {
    "aantal transacties": "aantal_transacties",
    "mediaan prijs(€)": "mediaan_prijs",
    "eerste kwartiel prijs(€)": "eerste_kwartiel_prijs",
    "derde kwartiel prijs(€)": "derde_kwartiel_prijs",
}


def _segment_slug(banner: Any) -> str | None:
    if not isinstance(banner, str):
        return None
    text = banner.strip().lower()
    return next((slug for prefix, slug in _SEGMENT_PREFIXES if text.startswith(prefix)), None)


def _flatten_header(banner_row: tuple[Any, ...], metric_row: tuple[Any, ...]) -> dict[int, str]:
    """Map column index -> flattened '{segment}__{metric}' (or key column) name.

    The banner names each segment once and is forward-filled across its metric
    columns. Columns without a recognised header (the spacers between segments
    and the trailing helper-formula column) are dropped here, explicitly."""
    columns: dict[int, str] = {}
    segment: str | None = None
    for index, metric in enumerate(metric_row):
        if index < len(banner_row) and (slug := _segment_slug(banner_row[index])):
            segment = slug
        if not isinstance(metric, str):
            continue
        name = metric.strip().lower()
        if name in _KEY_COLUMNS:
            columns[index] = name
        elif (metric_slug := _METRIC_SLUGS.get(name)) and segment is not None:
            columns[index] = f"{segment}__{metric_slug}"
    return columns


def load_property_sales_records(workbook_path: Path) -> list[PropertySalesRecord]:
    """Parse the Statbel per-municipality sales workbook into validated records.

    A row that fails validation is skipped (and logged with its identifier)
    rather than aborting the load: one malformed municipality row should not
    block the remaining ~37k statistical rows."""
    workbook = load_workbook(workbook_path, read_only=True)
    try:
        rows: Iterator[tuple[Any, ...]] = workbook.worksheets[0].iter_rows(values_only=True)
        banner_row: tuple[Any, ...] = ()
        for metric_row in rows:
            if metric_row and isinstance(metric_row[0], str) and metric_row[0].strip().lower() == "refnis":
                break
            banner_row = metric_row
        else:
            raise ValueError(f"{workbook_path}: no 'refnis' header row found")
        columns = _flatten_header(banner_row, metric_row)

        records: list[PropertySalesRecord] = []
        rows_read = rows_skipped = 0
        for row in rows:
            if all(cell is None for cell in row):
                continue
            rows_read += 1
            payload = {name: row[index] if index < len(row) else None for index, name in columns.items()}
            try:
                records.append(PropertySalesRecord.model_validate(payload))
            except ValidationError as error:
                rows_skipped += 1
                logger.warning(
                    "Skipping sales row refnis=%s jaar=%s periode=%s: %s",
                    payload.get("refnis"),
                    payload.get("jaar"),
                    payload.get("periode"),
                    error,
                )
        logger.info(
            "%s: %d rows read, %d parsed, %d skipped", workbook_path.name, rows_read, len(records), rows_skipped
        )
        return records
    finally:
        workbook.close()


def add_property_sales_record(database_path: Path, workbook_path: Path = STATISTICS_XLSX) -> None:
    """Load the Statbel quarterly sales-per-municipality workbook into the database."""
    records = load_property_sales_records(workbook_path)
    HuisVinderDb(database_path=database_path).add_property_sales_records(records)
