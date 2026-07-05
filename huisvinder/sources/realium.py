import datetime
from urllib.parse import urljoin

from huisvinder.models import BaseSource, BaseHouse
from huisvinder.utils import get_static_soup
from huisvinder.types import Sources


class Realium(BaseSource):
    """Realium is a new-build project developer: its overview page lists
    development projects without prices or unit details, so only
    project-level data can be collected."""

    name: Sources = "Realium"
    base_url: str = "https://www.realium.eu/realium-projecten"

    def _get_page_urls(self) -> list[str]:
        return [
            self.base_url,
        ]

    def _get_page_data(self, page_url: str) -> list[BaseHouse]:
        soup = get_static_soup(page_url)
        cards = soup.select("div.el-item")

        results = []
        for card in cards:
            link_tag = card.select_one("a.el-link") or card.find("a", href=True)
            if link_tag is None:
                continue
            link = urljoin("https://www.realium.eu/", str(link_tag["href"]))

            status_tag = card.select_one(".el-meta .field-value")
            status = status_tag.get_text(strip=True) if status_tag else None
            if status and status.lower() == "uitverkocht":
                continue

            city = None
            category = "Project"
            title_tag = card.select_one(".el-title")
            if title_tag:
                title = title_tag.get_text(strip=True)
                project, _, city_part = title.partition("|")
                category = project.strip() or category
                city = city_part.strip() or None

            description_tag = card.select_one(".el-content")
            description = description_tag.get_text(strip=True) if description_tag else None

            results.append(
                {
                    "source": self.name,
                    "created_at": datetime.date.today(),
                    "link": link,
                    "category": category,
                    "city": city,
                    "description": description,
                }
            )
        return [BaseHouse.model_validate(r) for r in results]
