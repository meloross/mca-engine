from __future__ import annotations

from app.adapters.florida.fl_ucc import FL_UCC_URL
from app.adapters.ucc.base_ucc_live import BaseUccLiveAdapter, HtmlFetcher


class FloridaUccLiveAdapter(BaseUccLiveAdapter):
    source_code = "FL_UCC_REGISTRY"
    state = "FL"
    base_url = FL_UCC_URL

    def __init__(self, html_fetcher: HtmlFetcher | None = None) -> None:
        super().__init__(html_fetcher=html_fetcher)
