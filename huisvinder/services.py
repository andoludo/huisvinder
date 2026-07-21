import logging
from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

import plotly.graph_objects as go
from openpyxl import load_workbook
from pydantic import ValidationError

from huisvinder.database.crud import HuisVinderDb
from huisvinder.details import enrich_houses
from huisvinder.models import BaseHouse, BaseSource, PropertySalesRecord, Simulation
from huisvinder.sources.bond_immo import BondImmo
from huisvinder.sources.bvm_vastgoed import BVMVastgoed
from huisvinder.sources.century_21 import Century21
from huisvinder.sources.covas import CovasImmo
from huisvinder.sources.de_immo_makelaar import DeImmoMakelaar
from huisvinder.sources.era_leuven import ERALeuven
from huisvinder.sources.era_vandendries import ERAVandendries
from huisvinder.sources.homies import Homies
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
from huisvinder.sources.vastgoed_sv import VastgoedSV
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
    Homies,
    VastgoedSV,
    BondImmo,
    ERALeuven,
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


class LocalityPrices(NamedTuple):
    """Weighted price summary for one municipality; None prices mean every quarter was suppressed."""

    locality: str
    median: float | None
    q1: float | None
    q3: float | None
    transactions: int
    periods: str


def _weighted_mean(values: list[tuple[float, int]]) -> float | None:
    if not values:
        return None
    total_weight = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / total_weight


def summarise_locality_prices(
    records: Sequence[PropertySalesRecord], localities: Sequence[str]
) -> list[LocalityPrices]:
    """Collapse quarterly Statbel rows into one price summary per municipality.

    Quarterly medians/quartiles are combined as a transaction-count-weighted
    mean: an approximation of the pooled statistic, not a true median, chosen
    because small municipalities have noisy latest quarters (often under 30
    transactions) or fully disclosure-suppressed ones. Suppressed (None) prices
    are excluded from the weighting but their transaction counts still add to
    the total. Localities without any usable price data are kept, with None
    prices. Sorted by affordability: cheapest weighted median first, no-data
    localities last.
    """
    by_locality: dict[str, list[PropertySalesRecord]] = {locality: [] for locality in localities}
    for record in records:
        by_locality.setdefault(record.locality, []).append(record)
    summaries = []
    for locality in localities:
        rows = by_locality[locality]
        transactions = sum(row.all_houses_transactions or 0 for row in rows)
        median, q1, q3 = (
            _weighted_mean(
                [
                    (float(value), row.all_houses_transactions or 1)
                    for row in rows
                    if (value := getattr(row, field)) is not None
                ]
            )
            for field in ("all_houses_median", "all_houses_q1", "all_houses_q3")
        )
        quarters = sorted((row.year, str(row.period)) for row in rows)
        periods = f"{quarters[0][0]} {quarters[0][1]} to {quarters[-1][0]} {quarters[-1][1]}" if quarters else "no data"
        summaries.append(LocalityPrices(locality, median, q1, q3, transactions, periods))
    return sorted(summaries, key=lambda summary: (summary.median is None, summary.median or 0.0))


# answer buckets for figure 1, in legend order; colours are colourblind-safe
_AFFORDABILITY_COLOURS = {
    "budget above Q3": "#1a9641",
    "budget above median": "#a6d96a",
    "budget below median": "#fdae61",
    "budget below Q1": "#d7191c",
}


def _affordability_bucket(budget: float, prices: LocalityPrices) -> str:
    if prices.median is None:
        return "insufficient data"
    q1 = prices.q1 if prices.q1 is not None else prices.median
    q3 = prices.q3 if prices.q3 is not None else prices.median
    if budget >= q3:
        return "budget above Q3"
    if budget >= prices.median:
        return "budget above median"
    if budget >= q1:
        return "budget below median"
    return "budget below Q1"


def _budget_figure(summaries: Sequence[LocalityPrices], budget: float) -> go.Figure:
    """Horizontal Q1-Q3 range per municipality, coloured by where the budget lands."""
    figure = go.Figure()
    buckets: dict[str, list[LocalityPrices]] = {}
    for summary in summaries:
        buckets.setdefault(_affordability_bucket(budget, summary), []).append(summary)
    for bucket, colour in _AFFORDABILITY_COLOURS.items():
        rows = buckets.get(bucket, [])
        if not rows:
            continue
        lows = [row.q1 if row.q1 is not None else row.median for row in rows]
        highs = [row.q3 if row.q3 is not None else row.median for row in rows]
        figure.add_bar(
            y=[row.locality for row in rows],
            base=lows,
            x=[high - low for high, low in zip(highs, lows, strict=True)],  # type: ignore[operator]
            orientation="h",
            name=bucket,
            marker_color=colour,
            customdata=[
                [low, row.median, high, row.transactions, row.periods]
                for row, low, high in zip(rows, lows, highs, strict=True)
            ],
            hovertemplate=(
                "%{y}<br>Q1 €%{customdata[0]:,.0f} | median €%{customdata[1]:,.0f} | Q3 €%{customdata[2]:,.0f}"
                "<br>%{customdata[3]} transactions | %{customdata[4]}<extra></extra>"
            ),
        )
    priced = [summary for summary in summaries if summary.median is not None]
    figure.add_scatter(
        y=[summary.locality for summary in priced],
        x=[summary.median for summary in priced],
        mode="markers",
        marker={"symbol": "line-ns", "size": 18, "line": {"width": 3, "color": "#222222"}},
        name="weighted median",
        hoverinfo="skip",
    )
    missing = [summary for summary in summaries if summary.median is None]
    if missing:
        figure.add_scatter(
            y=[summary.locality for summary in missing],
            x=[budget] * len(missing),
            mode="text",
            text=[f"insufficient data ({summary.transactions} transactions)" for summary in missing],
            textfont={"color": "#888888"},
            showlegend=False,
            hoverinfo="skip",
        )
    figure.add_vline(
        x=budget,
        line_dash="dash",
        line_color="#1f77b4",
        annotation_text=f"budget €{budget:,.0f}",
        annotation_position="top",
    )
    figure.update_layout(
        title={
            "text": "Budget versus market price per municipality"
            "<br><sub>Q1-Q3 range with weighted median; transaction-count-weighted mean of quarterly "
            "Statbel medians and quartiles (approximate, not a true pooled median)</sub>"
        },
        xaxis_title="price (EUR)",
        yaxis={"categoryorder": "array", "categoryarray": [summary.locality for summary in reversed(summaries)]},
        height=180 + 60 * len(summaries),
        legend_title="budget position",
    )
    return figure


# Flemish residential EPC label bands (kWh/m² per year) shaded behind figure 2
_EPC_BANDS: list[tuple[int, int | None, str, str]] = [
    (0, 100, "A", "#1a9641"),
    (100, 200, "B", "#a6d96a"),
    (200, 300, "C", "#ffffbf"),
    (300, 400, "D", "#fdae61"),
    (400, 500, "E", "#f46d43"),
    (500, None, "F", "#d7191c"),
]


def _epc_figure(houses: Sequence[BaseHouse], budget: float) -> go.Figure:
    """Price/EPC scatter per city; label-derived EPC estimates get a distinct marker."""
    figure = go.Figure()
    x_max = max((house.epc for house in houses if house.epc is not None), default=500) + 50
    for low, high, label, colour in _EPC_BANDS:
        figure.add_vrect(
            x0=low,
            x1=high if high is not None else max(x_max, 600),
            fillcolor=colour,
            opacity=0.12,
            line_width=0,
            layer="below",
            annotation_text=label,
            annotation_position="top",
        )
    by_city: dict[str, list[BaseHouse]] = {}
    for house in houses:
        by_city.setdefault(house.city or "unknown", []).append(house)
    for city, rows in sorted(by_city.items(), key=lambda item: -len(item[1])):
        figure.add_scatter(
            x=[house.epc for house in rows],
            y=[house.price for house in rows],
            mode="markers",
            name=f"{city} ({len(rows)})",
            marker={
                "size": 8,
                "symbol": ["diamond-open" if house.epc_is_estimated else "circle" for house in rows],
                "opacity": [0.45 if house.epc_is_estimated else 0.85 for house in rows],
            },
            customdata=[[house.bedrooms, str(house.category or "?"), house.link] for house in rows],
            hovertemplate=(
                city + " | €%{y:,.0f} | %{x} kWh/m²<br>bedrooms: %{customdata[0]} | %{customdata[1]}"
                "<br>%{customdata[2]}<extra></extra>"
            ),
        )
    figure.add_scatter(
        x=[None],
        y=[None],
        mode="markers",
        marker={"symbol": "diamond-open", "color": "#555555"},
        name="open diamond = label-derived EPC estimate",
        hoverinfo="skip",
    )
    figure.add_hline(
        y=budget,
        line_dash="dash",
        line_color="#1f77b4",
        annotation_text=f"budget €{budget:,.0f}",
        annotation_position="top right",
    )
    figure.update_layout(
        title={
            "text": "Price versus EPC for live house listings"
            "<br><sub>category 'house' only; x axis reversed so better energy performance sits to the right; "
            "shaded bands are the Flemish EPC label thresholds</sub>"
        },
        xaxis={"title": "EPC (kWh/m² per year)", "autorange": "reversed"},
        yaxis_title="price (EUR)",
        height=650,
        legend_title="city (listings)",
    )
    return figure


def create_report(
    database_path: Path,
    simulation: Simulation | None = None,
    output_path: Path | None = None,
) -> Path:
    """Write a self-contained interactive HTML report with both figures.

    plotly.js is inlined (roughly 4 MB) so the file opens fully offline.
    Returns the path of the written report (default: next to the database).
    """
    simulation = simulation or Simulation()
    output_path = output_path or database_path.with_suffix(".report.html")
    database = HuisVinderDb(database_path=database_path)
    summaries = summarise_locality_prices(
        database.get_sales_records(simulation.localities, simulation.min_year), simulation.localities
    )
    houses = database.get_priced_epc_houses()
    budget_figure = _budget_figure(summaries, simulation.budget)
    epc_figure = _epc_figure(houses, simulation.budget)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>HuisVinder report</title></head>
<body style="font-family: sans-serif; max-width: 1100px; margin: auto;">
<h1>HuisVinder report</h1>
<p>Budget €{simulation.budget:,.0f} | municipalities: {", ".join(simulation.localities)} |
statistics from {simulation.min_year} | generated {datetime.now():%Y-%m-%d %H:%M}</p>
<p>Figure 1 combines quarterly Statbel medians and quartiles as a transaction-count-weighted
mean, an approximation of the pooled statistics that is stable for small municipalities.</p>
<p><b>Caveat:</b> figure 1 is at Statbel municipality level, while figure 2 uses the scraped
listing city, which is often a sub-municipality (HEVERLEE, KESSEL-LO and WILSELE are part of
LEUVEN). No mapping between the two exists yet, so the figures are on different geographic
levels and cannot be compared city by city.</p>
{budget_figure.to_html(full_html=False, include_plotlyjs=True)}
{epc_figure.to_html(full_html=False, include_plotlyjs=False)}
</body></html>"""
    output_path.write_text(html, encoding="utf-8")
    logger.info("Report written to %s", output_path)
    return output_path
