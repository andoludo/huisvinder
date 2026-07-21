import shutil
from pathlib import Path

from huisvinder.models import PropertySalesRecord, Simulation
from huisvinder.services import create_report, summarise_locality_prices

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
    assert html.count("plotly-graph-div") >= 2
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
