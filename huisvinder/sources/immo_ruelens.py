import datetime

from bs4 import Tag

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup, normalize_epc
from huisvinder.types import Sources

MAX_PRICE = 400000
SOLD_STICKERS = {"verkocht", "recent verkocht"}


def _icon_value(card: Tag, icon_selector: str) -> str | None:
    icon = card.select_one(f".spotlight__hover {icon_selector}")
    if icon is None or icon.parent is None:
        return None
    value = icon.parent.get_text(strip=True)
    return value if value and value != "-" else None


class ImmoRuelens(BaseSource):
    name: Sources = "ImmoRuelens"
    base_url: str = f"https://www.immoruelens.be/nl/te-koop/?type%5B%5D=5&type%5B%5D=1&price-max={MAX_PRICE}"

    def _get_page_urls(self) -> list[str]:
        # all listings render on a single page
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("div.spotlight")

        results = []
        for card in cards:
            sticker_tag = card.select_one(".spotlight__image__sticker")
            sticker = sticker_tag.get_text(strip=True).lower() if sticker_tag else None
            if sticker in SOLD_STICKERS:
                continue

            link_tag = card.select_one(".spotlight__content a")
            if link_tag is None:
                continue
            link_path = str(link_tag["href"])
            # sold stock sometimes leaks in linking to /nl/verkocht/
            if not link_path.startswith("/nl/te-koop/"):
                continue
            link = f"https://www.immoruelens.be{link_path}"

            price_tag = card.select_one(".spotlight__content__price")
            if price_tag is None:
                continue
            price = price_tag.get_text(strip=True)

            city_tag = card.select_one(".spotlight__content__city")
            city = city_tag.get_text(strip=True) if city_tag else None

            epc = None
            epc_img = card.select_one(".spotlight__image__overlay-labels__energy-label img")
            if epc_img is not None:
                stem = str(epc_img.get("src", "")).rsplit("/", 1)[-1].removesuffix(".png")
                epc = normalize_epc(stem.removeprefix("epc_"))

            type_tag = card.select_one(".spotlight__content__type")
            category = type_tag.get_text(strip=True) if type_tag else None

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "display_price": price,
                    "epc": epc,
                    "bedrooms": _icon_value(card, "i.fa-bed"),
                    "living_area": _icon_value(card, "i.fa-home"),
                    "surface_ground": _icon_value(card, "span.icon-layers"),
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
