import logging
import os
import re
from functools import lru_cache
from time import sleep
from typing import Any

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
}
REQUEST_TIMEOUT = 30
REQUEST_DELAY_ENV = "HUISVINDER_REQUEST_DELAY"
DEFAULT_REQUEST_DELAY = 0.5


# first amount in strings like "€ 235.000", "€175.000", "294 900 € - 349 900 €"
PRICE_TOKEN = re.compile(r"\d{1,3}(?:[.\u00a0\u202f ]\d{3})+|\d+")


def parse_price(display_price: str) -> float | None:
    """Extract the (first) numeric amount from a display price string."""
    match = PRICE_TOKEN.search(display_price)
    if match is None:
        return None
    return float(re.sub(r"\D", "", match.group()))


def normalize_epc(raw: object) -> str | None:
    """Normalize EPC indicators like 'epc waarde f', 'a-plus' or 'c' to 'F'/'A+'/'C'."""
    if not raw:
        return None
    token = str(raw).strip().lower().removeprefix("epc waarde").strip()
    token = re.sub(r"[-_ ]?plus", "+", token)
    return token.upper() or None


def within_budget(display_price: str, max_price: int) -> bool:
    """Client-side price cap for sites without a server-side price filter.

    Prices that carry no amount at all (e.g. 'prijs op aanvraag') are kept,
    as they cannot be compared against the budget."""
    price = parse_price(display_price)
    if price is None:
        return True
    return price <= max_price


def request_delay() -> float:
    """Seconds slept before each request; override via HUISVINDER_REQUEST_DELAY."""
    return float(os.environ.get(REQUEST_DELAY_ENV, DEFAULT_REQUEST_DELAY))


@lru_cache(maxsize=1)
def _http_client() -> httpx.Client:
    # HTTP/2 matters: some sites (immoweb) reject plain HTTP/1.1 clients
    return httpx.Client(
        http2=True,
        headers=REQUEST_HEADERS,
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
)
def _fetch(url: str) -> httpx.Response:
    sleep(request_delay())
    logger.debug("GET %s", url)
    response = _http_client().get(url)
    response.raise_for_status()
    return response


def get_static_soup(url: str) -> BeautifulSoup:
    """Fetch a server-rendered page over plain HTTP and parse it."""
    return BeautifulSoup(_fetch(url).text, "html.parser")


def get_json(url: str) -> Any:
    """Fetch a JSON endpoint with the same politeness and retry policy."""
    return _fetch(url).json()
