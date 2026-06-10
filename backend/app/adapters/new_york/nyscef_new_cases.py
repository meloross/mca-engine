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
from app.adapters.new_york.mock_data import render_new_cases_html
from app.adapters.new_york.parsing import (
    compact_dict,
    parse_csv_rows,
    parse_date,
    parse_html_rows,
    split_names,
)

NYSCEF_NEW_CASES_URL = "https://iapps.courts.state.ny.us/nyscef/CaseSearch?TAB=courtDateRange"


class NyscefNewCasesAdapter(SourceAdapter):
    source_name = "NYSCEF New Cases Search"
    state = "NY"
    base_url = NYSCEF_NEW_CASES_URL
    terms_notes = (
        "Manual/import-first adapter. Live access is disabled until source terms are reviewed "
        "and automation is explicitly allowed. Do not bypass CAPTCHA or login controls."
    )
    automation_allowed = None

    async def fetch(self, params: dict[str, Any]) -> list[RawArtifact]:
        if self.mode == "mock":
            html = render_new_cases_html()
            return [
                self.save_raw_artifact(
                    content=html,
                    artifact_type="html",
                    source_url=self.base_url,
                    filename_hint="ny_nyscef_new_cases_mock",
                    metadata={"params": params, "access_method": "mock"},
                )
            ]

        if self.mode == "manual_import":
            artifacts: list[RawArtifact] = []
            for path in self.manual_files(suffixes=(".html", ".csv")):
                artifacts.append(self._save_manual_file(path, params=params))
            return artifacts

        self.assert_live_allowed()
        raise NotImplementedError("NYSCEF live access is disabled until terms allow automation.")

    async def parse(self, artifact: RawArtifact) -> list[ParsedRecord]:
        text = artifact.read_text()
        rows = (
            parse_csv_rows(text)
            if artifact.artifact_type == "csv"
            else parse_html_rows(text, record_name="case")
        )
        parsed: list[ParsedRecord] = []
        for row in rows:
            source_url = row.get("source_url") or artifact.source_url
            parsed.append(
                ParsedRecord(
                    record_type="case",
                    data={
                        "court_name": row.get("court_name"),
                        "county": row.get("county"),
                        "case_number": row.get("case_number"),
                        "caption": row.get("caption"),
                        "filing_date": row.get("filing_date"),
                        "case_type": row.get("case_type"),
                        "plaintiff_names": split_names(row.get("plaintiff_names")),
                        "defendant_names": split_names(row.get("defendant_names")),
                        "source_url": source_url,
                        "document_text": row.get("document_text"),
                    },
                    source_id=artifact.source_id,
                    source_url=source_url,
                    captured_at=artifact.captured_at,
                    raw_artifact_path=artifact.storage_path,
                )
            )
        self.audit("parsed", "Parsed NYSCEF new case rows.", count=len(parsed))
        return parsed

    async def normalize(self, record: ParsedRecord) -> NormalizedRecord:
        court_name = _required_string(record.data, "court_name")
        case_number = _required_string(record.data, "case_number")
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
            record_type="case",
            data=normalized_data,
            source_id=record.source_id,
            source_url=record.source_url,
            captured_at=record.captured_at,
            raw_artifact_path=record.raw_artifact_path,
            normalized_key=f"NY:CASE:{court_name.upper()}:{case_number.upper()}",
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
        raise ValueError(f"Missing required NYSCEF new case field: {key}")
    return value.strip()
