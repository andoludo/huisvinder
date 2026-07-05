import json
from pathlib import Path

from bs4 import BeautifulSoup

FIXTURES = Path(__file__).parent / "fixtures"

EMPTY_HTML = "<html><body><p>geen resultaten</p></body></html>"


def load_fixture_soup(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(), "html.parser")


def load_fixture_json(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())
