from __future__ import annotations

from app.adapters.new_york.ny_ucc import NY_UCC_URL
from app.adapters.ucc.base_ucc_live import BaseUccLiveAdapter, HtmlFetcher


class NewYorkUccLiveAdapter(BaseUccLiveAdapter):
    source_code = "NY_UCC_SEARCH"
    state = "NY"
    base_url = NY_UCC_URL

    def __init__(self, html_fetcher: HtmlFetcher | None = None) -> None:
        super().__init__(html_fetcher=html_fetcher)
