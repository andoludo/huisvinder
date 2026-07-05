import json
from pathlib import Path

from bs4 import BeautifulSoup

FIXTURES = Path(__file__).parent / "fixtures"

EMPTY_HTML = "<html><body><p>geen resultaten</p></body></html>"


def load_fixture_soup(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(), "html.parser")


def load_fixture_json(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


class FakeJsonResponse:
    """Minimal stand-in for requests.Response used by JSON-based sources."""

    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload
