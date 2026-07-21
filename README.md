# huisvinder

Scrapes houses and apartments for sale (≤ €400k, Leuven area, Belgium) from 21 real-estate sites into SQLite and CSV/JSON.

## Install

```sh
uv sync
```

## Usage

Pull every listing that is currently still available on the market:

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
| `--verbose, -v` | off | Debug logging |

`uv run huisvinder sources` lists all supported sources. `HUISVINDER_REQUEST_DELAY` (seconds, default `0.5`) sets the polite delay between requests.

## Supported sources

Immoweb, Immovlan, Realo, Century 21 Connect, Immo De Dijle, Immo Jan Stas, BVM Vastgoed, Immolight, Immo Horst, Marnix Vastgoed, Covas Immo, ImmoWonen, Your House Vastgoed, Immo Ter Duin, Realium, Immo-Time, José Ruelens, De Immo Makelaar, Immo GVE, We Invest Leuven, ERA Vandendries.

## How it works / limitations

Every source is scraped over plain HTTP (`httpx`, HTTP/2, retry with backoff) — either server-rendered HTML parsed with BeautifulSoup or the site's own JSON endpoint (Immoweb, We Invest, De Immo Makelaar). No browser automation. Sold / under-option listings are skipped; where a site offers no server-side price filter, the €400k cap is applied client-side. Search areas and the price cap are currently hard-coded per source.

Each listing stores the display price plus a derived numeric `price`, city, bedrooms, areas, `address`, `epc`, `garage` and `garden`. Address and EPC come from the listing cards where available; by default `pull` also fetches every listing's **detail page** (one extra request each) and fills the missing EPC/address/garage/garden from the spec tables all these sites render. Disable with `--no-details` for a fast card-only run. The €400k budget cap lives in `huisvinder/config.py` (`MAX_PRICE`).

Scrapers break when sites redesign. Offline fixture tests (`uv run pytest`) verify the parsers; `uv run pytest -m integration --no-cov` runs live smoke tests against the real sites to detect drift.

## Development

```sh
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy                  # types
uv run pytest                # offline tests + coverage
```
