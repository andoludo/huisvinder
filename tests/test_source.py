import logging
from pathlib import Path

import undetected_chromedriver as uc  # type: ignore[import-untyped]

from huisvinder.sources.century_21 import Century21
from huisvinder.sources.immodedijle import DeDijle
from huisvinder.sources.immovlan import Immovlan
from huisvinder.sources.immoweb import Immoweb
from huisvinder.sources.janstas import JanStas

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
    sources = []
    for url in urls[:3]:
        base_houses = immoweb._get_page_data(url)
        sources.extend(base_houses)
    assert sources


def test_immovlan() -> None:
    immovlan = Immovlan()
    urls = immovlan._get_page_urls()
    sources = []
    for url in urls[:3]:
        base_houses = immovlan._get_page_data(url)
        sources.extend(base_houses)
    assert sources


def test_immodedijle() -> None:
    dedijle = DeDijle()
    urls = dedijle._get_page_urls()
    sources = []
    for url in urls[:3]:
        base_houses = dedijle._get_page_data(url)
        sources.extend(base_houses)
    assert sources


def test_janstas() -> None:
    janstas = JanStas()
    urls = janstas._get_page_urls()
    sources = []
    for url in urls[:3]:
        base_houses = janstas._get_page_data(url)
        sources.extend(base_houses)
    assert sources
