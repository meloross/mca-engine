from __future__ import annotations

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
from app.adapters.new_york.mock_data import render_ucc_html
from app.adapters.new_york.parsing import compact_dict, parse_csv_rows, parse_date, parse_html_rows

NY_UCC_URL = "https://dos.ny.gov/uniform-commercial-code"


class NewYorkUccAdapter(SourceAdapter):
    source_name = "New York UCC Search"
    state = "NY"
    base_url = NY_UCC_URL
    terms_notes = (
        "Manual/import-first UCC adapter. Live automation is disabled until source terms, "
        "forms, and any payment restrictions are reviewed."
    )
    automation_allowed = None

    async def fetch(self, params: dict[str, Any]) -> list[RawArtifact]:
        if self.mode == "mock":
            html = render_ucc_html()
            return [
                self.save_raw_artifact(
                    content=html,
                    artifact_type="html",
                    source_url=self.base_url,
                    filename_hint="ny_ucc_search_mock",
                    metadata={"params": params, "access_method": "mock"},
                )
            ]

        if self.mode == "manual_import":
            artifacts: list[RawArtifact] = []
            for path in self.manual_files(suffixes=(".html", ".csv")):
                artifacts.append(self._save_manual_file(path, params=params))
            return artifacts

        self.assert_live_allowed()
        raise NotImplementedError("NY UCC live access is disabled until terms allow automation.")

    async def parse(self, artifact: RawArtifact) -> list[ParsedRecord]:
        text = artifact.read_text()
        rows = (
            parse_csv_rows(text)
            if artifact.artifact_type == "csv"
            else parse_html_rows(text, record_name="ucc")
        )
        parsed: list[ParsedRecord] = []
        for row in rows:
            source_url = row.get("source_url") or artifact.source_url
            parsed.append(
                ParsedRecord(
                    record_type="ucc_filing",
                    data={
                        "filing_number": row.get("filing_number"),
                        "filing_type": row.get("filing_type"),
                        "filing_date": row.get("filing_date"),
                        "debtor_name": row.get("debtor_name"),
                        "debtor_address": row.get("debtor_address"),
                        "secured_party_name": row.get("secured_party_name"),
                        "secured_party_address": row.get("secured_party_address"),
                        "collateral_text": row.get("collateral_text"),
                        "source_url": source_url,
                    },
                    source_id=artifact.source_id,
                    source_url=source_url,
                    captured_at=artifact.captured_at,
                    raw_artifact_path=artifact.storage_path,
                )
            )
        self.audit("parsed", "Parsed NY UCC rows.", count=len(parsed))
        return parsed

    async def normalize(self, record: ParsedRecord) -> NormalizedRecord:
        filing_number = _required_string(record.data, "filing_number")
        normalized_data = compact_dict(
            {
                **record.data,
                "state": self.state,
                "filing_date": parse_date(record.data.get("filing_date")),
                "source_id": record.source_id,
                "source_url": record.source_url,
                "captured_at": record.captured_at,
            }
        )
        return NormalizedRecord(
            record_type="ucc_filing",
            data=normalized_data,
            source_id=record.source_id,
            source_url=record.source_url,
            captured_at=record.captured_at,
            raw_artifact_path=record.raw_artifact_path,
            normalized_key=f"NY:UCC:{filing_number.upper()}",
        )

    def _save_manual_file(self, path: Path, *, params: dict[str, Any]) -> RawArtifact:
        artifact_type: AdapterArtifactType = "csv" if path.suffix.lower() == ".csv" else "html"
        return self.save_raw_artifact(
            content=path.read_bytes(),
            artifact_type=artifact_type,
            source_url=self.base_url,
            filename_hint=path.stem,
            metadata={
                "params": params,
                "access_method": "manual_import",
                "import_path": str(path),
            },
        )


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required NY UCC field: {key}")
    return value.strip()
