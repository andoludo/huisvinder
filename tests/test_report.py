import datetime
import shutil
from pathlib import Path

import pytest

from huisvinder.models import BaseHouse, PropertySalesRecord, Simulation
from huisvinder.services import (
    AMENITY_SYMBOLS,
    EPC_COLORS,
    _amenity_category,
    _epc_colour,
    _epc_label,
    _price_area_figure,
    create_report,
    summarise_locality_prices,
)

FIXTURE_DB = Path(__file__).parent / "sources" / "building.db"


def sales_row(locality, year=2024, period="Q1", transactions=10, median=None, q1=None, q3=None):  # noqa: PLR0913
    return PropertySalesRecord(
        nis_code="24001",
        locality=locality,
        year=year,
        period=period,
        all_houses_transactions=transactions,
        all_houses_median=median,
        all_houses_q1=q1,
        all_houses_q3=q3,
    )


def test_create_report_writes_both_figures(tmp_path: Path):
    database = tmp_path / "building.db"  # copy: opening the db runs migrations on it
    shutil.copy(FIXTURE_DB, database)
    output = tmp_path / "report.html"
    result = create_report(database, Simulation(), output_path=output)
    assert result == output
    html = output.read_text()
    assert len(html) > 100_000  # non-empty, with plotly.js inlined for offline use
    assert html.count("plotly-graph-div") >= 3
    assert "insufficient data" not in html or "HOLSBEEK" in html  # localities never silently dropped


def test_quarterly_medians_are_weighted_not_plain_mean():
    rows = [
        sales_row("LEUVEN", period="Q1", transactions=10, median=100_000),
        sales_row("LEUVEN", period="Q2", transactions=30, median=200_000),
    ]
    (summary,) = summarise_locality_prices(rows, ["LEUVEN"])
    assert summary.median == 175_000  # transaction-weighted; a plain mean would give 150_000
    assert summary.transactions == 40
    assert summary.periods == "2024 Q1 to 2024 Q2"


def test_suppressed_quarter_counts_transactions_but_not_prices():
    rows = [
        sales_row("HOLSBEEK", period="Q1", transactions=8),  # disclosure-suppressed prices
        sales_row("HOLSBEEK", period="Q2", transactions=12, median=300_000, q1=250_000, q3=350_000),
    ]
    (summary,) = summarise_locality_prices(rows, ["HOLSBEEK"])
    assert (summary.median, summary.q1, summary.q3) == (300_000, 250_000, 350_000)
    assert summary.transactions == 20


def test_locality_without_usable_data_is_kept_and_sorted_last():
    rows = [
        sales_row("HOLSBEEK", transactions=5),
        sales_row("BIERBEEK", transactions=20, median=350_000, q1=300_000, q3=400_000),
    ]
    summaries = summarise_locality_prices(rows, ["HOLSBEEK", "BIERBEEK"])
    assert [summary.locality for summary in summaries] == ["BIERBEEK", "HOLSBEEK"]
    assert summaries[-1].median is None
    assert summaries[-1].transactions == 5


def test_requested_locality_absent_from_database_still_appears():
    summaries = summarise_locality_prices([], ["NERGENS"])
    assert summaries[0].locality == "NERGENS"
    assert summaries[0].median is None
    assert summaries[0].periods == "no data"


def scatter_house(city="LEUVEN", price=300_000.0, living_area=120.0, **overrides) -> BaseHouse:
    # model_construct bypasses validation so raw casing/whitespace reaches the
    # figure helper, as it would when loading straight from the ORM
    return BaseHouse.model_construct(
        source="DeDijle",
        created_at=datetime.date.today(),
        link="https://example.test/1",
        city=city,
        price=price,
        living_area=living_area,
        **overrides,
    )


@pytest.mark.parametrize(
    ("garden", "garage", "expected"),
    [
        (True, True, "garden_and_garage"),
        (False, True, "garage_only"),
        (None, True, "garage_only"),
        (True, False, "garden_only"),
        (True, None, "garden_only"),
        (False, False, "none"),
        (None, None, "none"),  # unknown counts as absent
        (False, None, "none"),
    ],
)
def test_amenity_category(garden, garage, expected):
    house = scatter_house(garden=garden, garage=garage)
    assert _amenity_category(house) == expected
    assert AMENITY_SYMBOLS[expected]  # every bucket has a symbol


@pytest.mark.parametrize(
    ("epc", "label"),
    [(0, "A+"), (-5, "A+"), (50, "A"), (100, "B"), (450, "E"), (500, "F"), (1500, "F"), (None, None)],
)
def test_epc_label_bands(epc, label):
    assert _epc_label(epc) == label
    if label is None:
        assert _epc_colour(epc) not in EPC_COLORS.values()  # neutral grey, no crash
    else:
        assert _epc_colour(epc) == EPC_COLORS[label]


def test_price_area_figure_groups_cities_case_insensitively():
    houses = [
        scatter_house(city="Leuven"),
        scatter_house(city="leuven "),
        scatter_house(city=" LEUVEN"),
        scatter_house(city="Heverlee"),
        scatter_house(city=None),
        scatter_house(city="Tienen", price=None),  # dropped: no price
        scatter_house(city="Tienen", living_area=None),  # dropped: no living area
    ]
    figure = _price_area_figure(houses)
    city_traces = [trace for trace in figure.data if trace.legendgroup == "cities"]
    assert [trace.name for trace in city_traces] == ["LEUVEN (3)", "HEVERLEE (1)", "unknown (1)"]
    assert all(len(trace.x) == len(trace.y) for trace in city_traces)


def test_price_area_figure_reference_legends_and_marker_encoding():
    figure = _price_area_figure([scatter_house(epc=50, garden=True, garage=True)])
    (trace,) = [t for t in figure.data if t.legendgroup == "cities"]
    assert trace.marker.color == (EPC_COLORS["A"],)
    assert trace.marker.symbol == (AMENITY_SYMBOLS["garden_and_garage"],)
    swatches = [t for t in figure.data if t.legend == "legend2"]
    # one swatch per EPC band + unknown, plus one per amenity bucket
    assert len(swatches) == len(EPC_COLORS) + 1 + len(AMENITY_SYMBOLS)
    assert all(t.hoverinfo == "skip" for t in swatches)


def test_price_area_figure_empty_house_set_is_annotated_not_raised():
    figure = _price_area_figure([])
    assert not [trace for trace in figure.data if trace.legendgroup == "cities"]
    assert "no house listings" in figure.layout.annotations[0].text
