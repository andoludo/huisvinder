import csv
import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from huisvinder.database.crud import HuisVinderDb
from huisvinder.models import BaseHouse, BaseSource
from huisvinder.services import SOURCES, collect_houses, add_property_sales_record

app = typer.Typer(help="Scrape Leuven-area real-estate listings.", no_args_is_help=True)
logger = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _resolve_sources(names: list[str]) -> list[type[BaseSource]]:
    by_name = {str(source_class.model_fields["name"].default).lower(): source_class for source_class in SOURCES}
    resolved = []
    for name in names:
        source_class = by_name.get(name.lower())
        if source_class is None:
            known = ", ".join(sorted(by_name))
            raise typer.BadParameter(f"Unknown source {name!r}. Known sources: {known}")
        resolved.append(source_class)
    return resolved


def _write_output(houses: list[BaseHouse], output: Path) -> None:
    rows = [house.model_dump(mode="json") for house in houses]
    if output.suffix.lower() == ".json":
        output.write_text(json.dumps(rows, indent=1))
        return
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(BaseHouse.model_fields))
        writer.writeheader()
        writer.writerows(rows)


@app.command()
def pull(
    db: Annotated[Path, typer.Option(help="SQLite database the listings are upserted into.")] = Path("building.db"),
    output: Annotated[Path, typer.Option(help="Output file; .csv or .json by extension.")] = Path("houses.csv"),
    source: Annotated[
        list[str] | None,
        typer.Option("--source", "-s", help="Only pull these sources (repeatable); default: all."),
    ] = None,
    details: Annotated[
        bool,
        typer.Option(
            "--details/--no-details",
            help="Also fetch each listing's detail page for epc/address/garage/garden.",
        ),
    ] = True,
    available_only: Annotated[
        bool,
        typer.Option("--available-only", help="Drop sold / under-option listings."),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Pull all houses currently still available on the market."""
    _configure_logging(verbose)
    source_classes = _resolve_sources(source) if source else None
    houses = collect_houses(source_classes, with_details=details)
    if available_only:
        houses = [house for house in houses if house.status == "available"]
    HuisVinderDb(database_path=db).add_houses(houses)
    _write_output(houses, output)
    logger.info("Wrote %d available listings to %s (database: %s)", len(houses), output, db)


@app.command()
def fetch(
    database: Annotated[Path, typer.Argument(help="SQLite database the listings are upserted into.")],
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")] = False,
) -> None:
    """Fetch all houses from every source with full details into a database."""
    _configure_logging(verbose)
    add_property_sales_record(database)
    houses = collect_houses(with_details=True)
    HuisVinderDb(database_path=database).add_houses(houses)
    logger.info("Stored %d available listings in %s", len(houses), database)


@app.command()
def sources() -> None:
    """List the supported listing sources."""
    _configure_logging(verbose=False)
    for source_class in SOURCES:
        logger.info(
            "%s (%s)",
            source_class.model_fields["name"].default,
            source_class.model_fields["base_url"].default,
        )


if __name__ == "__main__":
    app()
