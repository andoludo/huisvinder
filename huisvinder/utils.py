import logging
import re
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from time import sleep
from typing import Any
from collections.abc import Callable, Generator

import requests
import undetected_chromedriver as uc  # type: ignore[import-untyped] # no stubs shipped
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

REQUEST_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
}
REQUEST_TIMEOUT = 30


def within_budget(display_price: str, max_price: int) -> bool:
    """Client-side price cap for sites without a server-side price filter.

    Prices that carry no digits at all (e.g. 'prijs op aanvraag') are kept,
    as they cannot be compared against the budget."""
    digits = re.sub(r"\D", "", display_price)
    if not digits:
        return True
    return int(digits) <= max_price


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8.0),
)
def get_static_soup(url: str) -> BeautifulSoup:
    """Fetch a server-rendered page over plain HTTP and parse it.

    Much more robust than driving a browser for sites that do not require
    JavaScript to render their listings."""
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


@contextmanager
def web_browser(
    url: str,
    load_strategy_none: bool = False,
    headless: bool = False,
    callback: Callable[[WebDriver], None] | None = None,
) -> Generator[WebDriver, Any, None]:
    browser = uc.Chrome(headless=headless, use_subprocess=False)
    browser.set_page_load_timeout(30)

    try:
        browser.get(url)
        sleep(30)
    except Exception:
        browser.execute_script("window.stop();")
    if callback:
        sleep(10)
        callback(browser)
    sleep(2)
    yield browser
    browser.quit()


@contextmanager
def soup_page(browser: WebDriver) -> Generator[BeautifulSoup, Any, None]:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=True) as page:
        page_source_code = browser.page_source.encode("utf-8")
        Path(page.name).write_bytes(page_source_code)
        yield BeautifulSoup(page, "html.parser")


@contextmanager
def temporary_web_page(
    url: str,
    load_strategy_none: bool = False,
    headless: bool = False,
    callback: Callable[[WebDriver], None] | None = None,
) -> Generator[BeautifulSoup, Any, None]:
    with web_browser(url, load_strategy_none, headless, callback=callback) as browser, soup_page(browser) as soup:
        yield soup
        browser.quit()


def find_cookie_banner(browser: WebDriver, xpath: str, iframe: str | None = None) -> None:
    if iframe is None:
        try:
            button = browser.find_element(By.XPATH, xpath)
            if button:
                time.sleep(5)
                button.click()
        except Exception as e:
            logger.warning(f"Cookie banner: {e}")
    else:
        try:
            WebDriverWait(browser, 10).until(
                expected_conditions.frame_to_be_available_and_switch_to_it((By.XPATH, iframe))
            )
            WebDriverWait(browser, 10).until(expected_conditions.element_to_be_clickable((By.XPATH, xpath))).click()
            browser.switch_to.default_content()
        except Exception as e:
            logger.warning(f"Cookie banner: {e}")


def scroll_to_bottom(driver: WebDriver, pause_time: int = 2) -> None:
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:
            break

        last_height = new_height
