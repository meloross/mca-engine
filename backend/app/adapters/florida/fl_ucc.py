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
from app.adapters.florida.mock_data import render_ucc_html
from app.adapters.parsing import (
    compact_dict,
    parse_csv_rows,
    parse_date,
    parse_datetime,
    parse_html_rows,
)

FL_UCC_URL = "https://floridaucc.com/"


class FloridaUccAdapter(SourceAdapter):
    source_name = "Florida Secured Transaction Registry"
    state = "FL"
    base_url = FL_UCC_URL
    terms_notes = (
        "Manual/import-first UCC adapter for saved Florida Secured Transaction Registry "
        "search results. Live access is gated behind source terms review and feature flag."
    )
    automation_allowed = None

    async def fetch(self, params: dict[str, Any]) -> list[RawArtifact]:
        if self.mode == "mock":
            return [
                self.save_raw_artifact(
                    content=render_ucc_html(),
                    artifact_type="html",
                    source_url=self.base_url,
                    filename_hint="fl_ucc_mock",
                    metadata={"params": params, "access_method": "mock"},
                )
            ]

        if self.mode == "manual_import":
            artifacts: list[RawArtifact] = []
            for path in self.manual_files(suffixes=(".html", ".csv", ".pdf")):
                artifacts.append(self._save_manual_file(path, params=params))
            return artifacts

        self.assert_live_allowed()
        raise NotImplementedError(
            "Florida UCC live access is disabled until terms allow automation."
        )

    async def parse(self, artifact: RawArtifact) -> list[ParsedRecord]:
        rows = _rows_from_artifact(artifact)
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
                        "source_timestamp": row.get("source_timestamp"),
                        "access_method": artifact.metadata.get("access_method", self.mode),
                    },
                    source_id=artifact.source_id,
                    source_url=source_url,
                    captured_at=artifact.captured_at,
                    raw_artifact_path=artifact.storage_path,
                )
            )
        self.audit("parsed", "Parsed Florida UCC rows.", count=len(parsed))
        return parsed

    async def normalize(self, record: ParsedRecord) -> NormalizedRecord:
        filing_number = _required_string(record.data, "filing_number")
        normalized_data = compact_dict(
            {
                **record.data,
                "state": self.state,
                "filing_date": parse_date(record.data.get("filing_date")),
                "source_timestamp": parse_datetime(record.data.get("source_timestamp")),
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
            normalized_key=f"FL:UCC:{filing_number.upper()}",
        )

    def _save_manual_file(self, path: Path, *, params: dict[str, Any]) -> RawArtifact:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            artifact_type: AdapterArtifactType = "csv"
        elif suffix == ".pdf":
            artifact_type = "pdf"
        else:
            artifact_type = "html"
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


def _rows_from_artifact(artifact: RawArtifact) -> list[dict[str, str]]:
    if artifact.artifact_type == "csv":
        return parse_csv_rows(artifact.read_text())
    if artifact.artifact_type == "pdf":
        return []
    return parse_html_rows(artifact.read_text(), record_name="ucc")


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required Florida UCC field: {key}")
    return value.strip()
