from bs4 import BeautifulSoup

from huisvinder.config import MAX_PRICE
from huisvinder.models import BaseHouse, BaseSource
from huisvinder.sources._era import parse_era_card
from huisvinder.types import Sources
from huisvinder.utils import get_json

# era.be facet ids: property_type 46 = house; municipalities and
# sub-municipalities cover Leuven and its surrounding villages
MUNICIPALITIES = "464+216"
SUB_MUNICIPALITIES = "1491+1611+2764+2773+1633+1771+2089"
PAGE_SIZE = 12  # the API rejects limits that are not a multiple of 12


class ERALeuven(BaseSource):
    """All ERA offices' houses around Leuven, via the era.be search API
    (unlike ERAVandendries, which is broker-scoped). The server-rendered
    search page ignores the location facets, but the JSON API applies them
    and returns the same card markup in each result's teaser."""

    name: Sources = "ERALeuven"
    base_url: str = (
        "https://www.era.be/en/jsonapi/index/property_index"
        "?filter%5Bsale_or_rent%5D=sale"
        "&filter%5Bproperty_type%5D=46"
        f"&filter%5Bprice%5D=%28min%3A%3Bmax%3A{MAX_PRICE}%29"
        "&filter%5Bamount_bedrooms%5D=%28min%3A2%3Bmax%3A%29"
        f"&filter%5Blocation%5D%5Bmunicipalities%5D={MUNICIPALITIES}"
        f"&filter%5Blocation%5D%5Bsub_municipalities%5D={SUB_MUNICIPALITIES}"
        f"&pager%5Blimit%5D={PAGE_SIZE}"
    )

    def _get_page_urls(self) -> list[str]:
        max_page = 3
        return [f"{self.base_url}&pager%5Boffset%5D={page_number * PAGE_SIZE}" for page_number in range(max_page)]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        payload = get_json(page_url)
        results = []
        for item in payload.get("data", []):
            teaser = (item.get("attributes") or {}).get("teaser") or ""
            card = BeautifulSoup(teaser, "html.parser").select_one("article.node--property[about]")
            if card is None:
                continue
            house = parse_era_card(card, self.name)
            if house is not None:
                results.append(house)
        return results
