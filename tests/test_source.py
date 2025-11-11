import logging
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from time import sleep
from typing import Optional, Generator, Any, Callable
import undetected_chromedriver as uc  # type: ignore[import-untyped]
from bs4 import BeautifulSoup
from pydantic import BaseModel, model_validator
from selenium.webdriver.chrome.webdriver import WebDriver

from huisvinder.sources.century_21 import Century21
from huisvinder.sources.immoweb import Immoweb

logger = logging.getLogger(__name__)
PAGE_SOURCE_PATH = Path(__file__).parents[1] / "tests" / "sources"


def test_century() -> None:
    century_21 = Century21()
    urls = century_21._get_page_urls()
    base_houses = century_21._get_page_data(urls[0])
    assert base_houses


def test_immoweb() -> None:
    immoweb = Immoweb()
    urls = immoweb._get_page_urls()
    base_houses = immoweb._get_page_data(urls[0])
    assert base_houses
