from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.adapters.base import (
    ArtifactType as AdapterArtifactType,
)
from app.adapters.base import (
    NormalizedRecord,
    ParsedRecord,
    RawArtifact,
    SourceAdapter,
)


@dataclass(frozen=True)
class CountyClerkConfig:
    county: str
    base_url: str
    search_strategy: str
    manual_import_parser: str


INITIAL_FLORIDA_COUNTY_CLERKS: tuple[CountyClerkConfig, ...] = (
    CountyClerkConfig(
        "Miami-Dade",
        "https://www2.miamidadeclerk.gov/ocs/",
        "manual",
        "saved_html_csv_pdf",
    ),
    CountyClerkConfig(
        "Broward",
        "https://www.browardclerk.org/",
        "manual",
        "saved_html_csv_pdf",
    ),
    CountyClerkConfig(
        "Palm Beach",
        "https://appsgp.mypalmbeachclerk.com/eCaseView/",
        "manual",
        "saved_html_csv_pdf",
    ),
    CountyClerkConfig(
        "Orange",
        "https://myeclerk.myorangeclerk.com/",
        "manual",
        "saved_html_csv_pdf",
    ),
    CountyClerkConfig(
        "Hillsborough",
        "https://hover.hillsclerk.com/",
        "manual",
        "saved_html_csv_pdf",
    ),
    CountyClerkConfig(
        "Pinellas",
        "https://ccmspa.pinellascounty.org/",
        "manual",
        "saved_html_csv_pdf",
    ),
    CountyClerkConfig("Duval", "https://core.duvalclerk.com/", "manual", "saved_html_csv_pdf"),
    CountyClerkConfig("Polk", "https://pro.polkcountyclerk.net/", "manual", "saved_html_csv_pdf"),
    CountyClerkConfig("Lee", "https://matrix.leeclerk.org/", "manual", "saved_html_csv_pdf"),
    CountyClerkConfig(
        "Collier",
        "https://cms.collierclerk.com/",
        "manual",
        "saved_html_csv_pdf",
    ),
    CountyClerkConfig(
        "Seminole",
        "https://courtrecords.seminoleclerk.org/",
        "manual",
        "saved_html_csv_pdf",
    ),
    CountyClerkConfig(
        "Osceola",
        "https://courts.osceolaclerk.com/",
        "manual",
        "saved_html_csv_pdf",
    ),
)


class FloridaCountyClerkBaseAdapter(SourceAdapter):
    state = "FL"
    terms_notes = (
        "County clerk base adapter. Manual import and mock support only until each county's "
        "terms and access controls are reviewed. Do not bypass CAPTCHA, login, or access controls."
    )
    automation_allowed = None

    def __init__(
        self,
        *,
        county_config: CountyClerkConfig,
        manual_parser: Callable[[RawArtifact], list[ParsedRecord]],
        **kwargs: Any,
    ) -> None:
        self.county = county_config.county
        self.base_url = county_config.base_url
        self.source_name = f"Florida {county_config.county} County Clerk Manual Records"
        self.search_strategy = county_config.search_strategy
        self.manual_import_parser = county_config.manual_import_parser
        self._manual_parser = manual_parser
        super().__init__(**kwargs)

    async def fetch(self, params: dict[str, Any]) -> list[RawArtifact]:
        if self.mode == "manual_import":
            artifacts: list[RawArtifact] = []
            for path in self.manual_files(suffixes=(".html", ".csv", ".pdf", ".txt")):
                artifacts.append(
                    self.save_raw_artifact(
                        content=path.read_bytes(),
                        artifact_type=_artifact_type(path),
                        source_url=self.base_url,
                        filename_hint=path.stem,
                        metadata={
                            "params": params,
                            "access_method": "manual_import",
                            "county": self.county,
                            "import_path": str(path),
                        },
                    )
                )
            return artifacts

        if self.mode == "mock":
            return []

        self.assert_live_allowed()
        raise NotImplementedError("County clerk live access is disabled until terms allow it.")

    async def parse(self, artifact: RawArtifact) -> list[ParsedRecord]:
        return self._manual_parser(artifact)

    @abstractmethod
    async def normalize(self, record: ParsedRecord) -> NormalizedRecord:
        raise NotImplementedError


def _artifact_type(path: Path) -> AdapterArtifactType:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".html":
        return "html"
    return "txt"
