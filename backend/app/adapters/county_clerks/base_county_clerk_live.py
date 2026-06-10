from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ManualImportParser = Callable[[str], list[dict[str, object]]]


@dataclass(frozen=True)
class CountyClerkConfig:
    county: str
    state: str
    base_url: str
    search_strategy: str
    automation_allowed: bool | None = None
    enabled: bool = False


class CountyClerkLiveAdapter:
    def __init__(
        self,
        config: CountyClerkConfig,
        *,
        manual_import_parser: ManualImportParser | None = None,
    ) -> None:
        self.config = config
        self.manual_import_parser = manual_import_parser

    def status(self) -> dict[str, object]:
        return {
            "county": self.config.county,
            "state": self.config.state,
            "base_url": self.config.base_url,
            "search_strategy": self.config.search_strategy,
            "enabled": self.config.enabled,
            "automation_allowed": self.config.automation_allowed,
            "message": "Manual import placeholder; no unsafe scraping implemented.",
        }
