# huisvinder

Scrapes houses and apartments for sale (≤ €500k, Leuven area, Belgium) from 27 real-estate sites into SQLite and CSV/JSON.

## Install

```sh
uv sync
```

## Usage

Fetch every available listing from all sources, with full details, into a database — only the database path is needed:

```sh
uv run huisvinder fetch building.db
```

For more control, `pull` also writes an output file and can limit sources:

```sh
uv run huisvinder pull
```

This writes `houses.csv` and upserts into `building.db`. Rows are keyed on `(source, created_at, link)`, so a daily run builds a history of what was on the market when.

### Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `--db PATH` | `building.db` | SQLite database to upsert into |
| `--output PATH` | `houses.csv` | Output file; `.csv` or `.json` by extension |
| `--source, -s NAME` | all | Only pull these sources (repeatable), e.g. `-s immoweb -s dedijle` |
| `--details / --no-details` | on | Fetch each listing's detail page for EPC/address/garage/garden |
| `--available-only` | off | Drop sold / under-option listings |
| `--verbose, -v` | off | Debug logging |

`uv run huisvinder sources` lists all supported sources. `HUISVINDER_REQUEST_DELAY` (seconds, default `0.5`) sets the polite delay between requests.

### Report

Generate a self-contained interactive HTML report (opens offline, plotly.js inlined) from a fetched database:

```sh
uv run huisvinder report building.db
```

This writes `building.report.html` next to the database, with two figures: your budget against the Statbel Q1–Q3 house-price range per municipality (quarterly medians combined as a transaction-count-weighted mean, an approximation of the pooled statistics), and price versus EPC for live house listings (label-derived EPC estimates are drawn as open diamonds). Note the two figures are on different geographic levels: Statbel municipalities versus scraped listing cities, which are often sub-municipalities.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--budget EUR` | `400000` | Purchase budget, drawn as a reference line in both figures |
| `--locality, -l NAME` | `BIERBEEK, HOLSBEEK, LEUVEN, OUD-HEVERLEE, LUBBEEK` | Statbel municipality to compare (repeatable) |
| `--min-year YEAR` | `2023` | First Statbel year to include |
| `--output PATH` | `<database>.report.html` | Output HTML path |

## Supported sources

Immoweb, Immovlan, Realo, Homies, Century 21 Connect, Immo De Dijle, Immo Jan Stas, BVM Vastgoed, Immolight, Immo Horst, Marnix Vastgoed, Covas Immo, ImmoWonen, Your House Vastgoed, Immo Ter Duin, Realium, Immo-Time, José Ruelens, De Immo Makelaar, Immo GVE, We Invest Leuven, ERA Vandendries, ERA Leuven-region search, Vastgoed SV, Bond Immo, KDC Immo, Polares.

## How it works / limitations

Every source is scraped over plain HTTP (`httpx`, HTTP/2, retry with backoff) — either server-rendered HTML parsed with BeautifulSoup or the site's own JSON endpoint (Immoweb, We Invest, De Immo Makelaar). No browser automation. Where a site offers no server-side price filter, the €500k cap is applied client-side. Search areas are currently hard-coded per source.

Each listing stores the display price plus a derived numeric `price`, city, bedrooms, areas, `address`, `epc`, `garage`, `garden` and a normalized `status` (`available` / `option` / `sold`) taken from the sites' sold- and option-badges, so genuinely available houses are easy to single out (`WHERE status = 'available'` or `pull --available-only`). Sold cards that carry no link cannot be stored and are skipped. Address and EPC come from the listing cards where available; by default `pull` also fetches every listing's **detail page** (one extra request each) and fills the missing EPC/address/garage/garden from the spec tables all these sites render. Disable with `--no-details` for a fast card-only run. The budget cap lives in `huisvinder/config.py` (`MAX_PRICE`).

Scrapers break when sites redesign. Offline fixture tests (`uv run pytest`) verify the parsers; `uv run pytest -m integration --no-cov` runs live smoke tests against the real sites to detect drift.

## Development

```sh
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy                  # types
uv run pytest                # offline tests + coverage
```
