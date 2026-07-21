from huisvinder.sources._whise import WhiseGridSource
from huisvinder.types import Sources


class VastgoedSV(WhiseGridSource):
    name: Sources = "VastgoedSV"
    base_url: str = "https://www.vastgoedsv.be/nl/te-koop"

    def _get_page_urls(self) -> list[str]:
        # small agency: the site echoes page 1 for any /page-N, so single page
        return [
            self.base_url,
        ]
