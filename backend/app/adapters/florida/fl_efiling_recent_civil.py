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
from app.adapters.florida.mock_data import render_civil_html
from app.adapters.parsing import (
    compact_dict,
    parse_csv_rows,
    parse_date,
    parse_datetime,
    parse_html_rows,
    split_names,
    truthy_text,
)

FL_EFILING_URL = "https://myflcourtaccess.com/authority/"


class FloridaEfilingRecentCivilAdapter(SourceAdapter):
    source_name = "Florida Statewide Non-Confidential Circuit Civil Filings"
    state = "FL"
    base_url = FL_EFILING_URL
    terms_notes = (
        "Manual/import-first adapter for downloaded non-confidential Florida civil filing "
        "exports. Portal access may require registered account access; credentials must never "
        "be hardcoded. Do not bypass login, CAPTCHA, or access controls."
    )
    automation_allowed = None

    async def fetch(self, params: dict[str, Any]) -> list[RawArtifact]:
        if self.mode == "mock":
            return [
                self.save_raw_artifact(
                    content=render_civil_html(),
                    artifact_type="html",
                    source_url=self.base_url,
                    filename_hint="fl_efiling_recent_civil_mock",
                    metadata={"params": params, "access_method": "mock"},
                )
            ]

        if self.mode == "manual_import":
            artifacts: list[RawArtifact] = []
            for path in self.manual_files(suffixes=(".html", ".csv", ".pdf")):
                artifacts.append(self._save_manual_file(path, params=params))
            return artifacts

        self.assert_live_allowed()
        raise NotImplementedError("Florida e-filing live access is disabled until terms allow it.")

    async def parse(self, artifact: RawArtifact) -> list[ParsedRecord]:
        rows = _rows_from_artifact(artifact, record_name="civil_filing")
        parsed: list[ParsedRecord] = []
        for row in rows:
            if _is_restricted(row):
                self.audit(
                    "record_excluded",
                    "Skipped confidential/restricted Florida civil filing.",
                    source_url=row.get("source_url") or artifact.source_url,
                )
                continue

            source_url = row.get("source_url") or artifact.source_url
            parsed.append(
                ParsedRecord(
                    record_type="case",
                    data={
                        "county": row.get("county"),
                        "court_name": row.get("court_name"),
                        "case_number": row.get("case_number"),
                        "filing_date": row.get("filing_date"),
                        "caption": row.get("caption"),
                        "plaintiff_names": split_names(row.get("plaintiff_names")),
                        "defendant_names": split_names(row.get("defendant_names")),
                        "document_title": row.get("document_title"),
                        "document_text": row.get("document_text"),
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
        self.audit("parsed", "Parsed Florida recent civil filing rows.", count=len(parsed))
        return parsed

    async def normalize(self, record: ParsedRecord) -> NormalizedRecord:
        court_name = _required_string(record.data, "court_name")
        case_number = str(record.data.get("case_number") or record.data.get("caption") or "")
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
            record_type="case",
            data=normalized_data,
            source_id=record.source_id,
            source_url=record.source_url,
            captured_at=record.captured_at,
            raw_artifact_path=record.raw_artifact_path,
            normalized_key=f"FL:CASE:{court_name.upper()}:{case_number.upper()}",
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


def _rows_from_artifact(artifact: RawArtifact, *, record_name: str) -> list[dict[str, str]]:
    if artifact.artifact_type == "csv":
        return parse_csv_rows(artifact.read_text())
    if artifact.artifact_type == "pdf":
        return []
    return parse_html_rows(artifact.read_text(), record_name=record_name)


def _is_restricted(row: dict[str, str]) -> bool:
    access_status = str(row.get("access_status") or "").strip().lower()
    return truthy_text(row.get("is_confidential")) or access_status in {
        "confidential",
        "restricted",
        "sealed",
    }


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required Florida civil filing field: {key}")
    return value.strip()
