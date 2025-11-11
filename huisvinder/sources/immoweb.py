import datetime
import time
from typing import List, Optional

from pydantic import BaseModel
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from undetected_chromedriver import WebElement  # type: ignore

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.services import web_browser
from huisvinder.types import Sources


class Selector(BaseModel):
    selector: str
    attribute: Optional[str] = None
    name: str


def remove_banner(browser: WebDriver) -> None:
    host = WebDriverWait(browser, 30).until(
        expected_conditions.presence_of_element_located((By.XPATH, "/html/body/div[5]"))
    )
    for _ in range(60):  # 10 checks per second
        shadow = browser.execute_script("return arguments[0].shadowRoot", host)
        if shadow is not None:
            break
        time.sleep(1)
    if shadow is None:
        raise Exception("No shadow found")
    ok_button = shadow.find_element(
        By.CSS_SELECTOR,
        "#uc-center-container > div.sc-eBMEME.ixkACg > div > div.sc-jsJBEP.jnQAFK > div > button.sc-dcJsrY.liDFoy",
    )
    ok_button.click()


def _get_data(
    item: WebElement, css_selector: str, attribute: Optional[str] = None
) -> Optional[str]:
    try:
        if attribute:
            return item.find_element(By.CSS_SELECTOR, css_selector).get_attribute(  # type: ignore
                attribute
            )
        return item.find_element(By.CSS_SELECTOR, css_selector).text  # type: ignore
    except Exception:
        return None


SELECTORS = [
    Selector(name="link", attribute="href", selector="article a"),
    Selector(name="display_price", selector=".card--result__price .resizable-text"),
    Selector(
        name="city", selector=".card__information.card--results__information--locality"
    ),
    Selector(name="description", selector=".card--result__description"),
    Selector(
        name="bedrooms",
        selector=(
            ".card__information.card--result__information.card__information--property"
            " > span:nth-child(1) > span:nth-child(1)"
        ),
    ),
]


class Immoweb(BaseSource):
    name: Sources = "Immoweb"
    base_url: str = (
        "https://www.immoweb.be/en/search/house-and-apartment/for-sale?buildingConditions=GOOD,JUST_RENOVATED,"
        "TO_RENOVATE&countries=BE&epcScores=E,D,C,F,B,A&maxPrice=400000&minBedroomCount=2&postalCodes="
        "BE-3001,3000&page=1&orderBy=relevance"
    )

    def _get_page_urls(self) -> list[str]:
        max_page = 15
        return [
            self.base_url,
            *[
                self.base_url.replace("&page=1&", f"&page={page_number}&")
                for page_number in range(2, max_page + 1)
            ],
        ]

    def _get_page_data(self, page_url: str) -> List[BaseHouse]:
        with web_browser(page_url, headless=False, callback=remove_banner) as browser:

            items = browser.find_elements(By.CSS_SELECTOR, "li.search-results__item")
            results = []
            for item in items:
                search_result = {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                }
                for selector in SELECTORS:
                    value = _get_data(item, selector.selector, selector.attribute)
                    search_result.update({selector.name: value})  # type: ignore
                if search_result.get("link"):
                    results.append(search_result)
            return [BaseHouse.model_validate(r) for r in results]
