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
from app.adapters.florida.mock_data import render_business_entities_csv
from app.adapters.parsing import compact_dict, parse_csv_rows, parse_datetime, parse_html_rows
from app.compliance import normalize_business_name

FL_SUNBIZ_DOWNLOADS_URL = "https://dos.fl.gov/sunbiz/other-services/data-downloads/"


class FloridaBusinessEntitiesAdapter(SourceAdapter):
    source_name = "Florida Division of Corporations Data Downloads"
    state = "FL"
    base_url = FL_SUNBIZ_DOWNLOADS_URL
    terms_notes = (
        "Manual/import-first business enrichment adapter for saved Sunbiz daily or quarterly "
        "data files. Use official downloads; do not automate restricted flows."
    )
    automation_allowed = None

    async def fetch(self, params: dict[str, Any]) -> list[RawArtifact]:
        if self.mode == "mock":
            return [
                self.save_raw_artifact(
                    content=render_business_entities_csv(),
                    artifact_type="csv",
                    source_url=self.base_url,
                    filename_hint="fl_business_entities_mock",
                    metadata={"params": params, "access_method": "mock"},
                )
            ]

        if self.mode == "manual_import":
            artifacts: list[RawArtifact] = []
            for path in self.manual_files(suffixes=(".csv", ".html")):
                artifacts.append(self._save_manual_file(path, params=params))
            return artifacts

        self.assert_live_allowed()
        raise NotImplementedError("Florida Sunbiz live access is disabled until terms allow it.")

    async def parse(self, artifact: RawArtifact) -> list[ParsedRecord]:
        rows = (
            parse_csv_rows(artifact.read_text())
            if artifact.artifact_type == "csv"
            else parse_html_rows(artifact.read_text(), record_name="business_entity")
        )
        parsed: list[ParsedRecord] = []
        for row in rows:
            source_url = row.get("source_url") or artifact.source_url
            parsed.append(
                ParsedRecord(
                    record_type="business_entity",
                    data={
                        "entity_name": row.get("entity_name"),
                        "entity_type": row.get("entity_type"),
                        "status": row.get("status"),
                        "principal_address": row.get("principal_address"),
                        "mailing_address": row.get("mailing_address"),
                        "registered_agent_name": row.get("registered_agent_name"),
                        "registered_agent_address": row.get("registered_agent_address"),
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
        self.audit("parsed", "Parsed Florida business entity rows.", count=len(parsed))
        return parsed

    async def normalize(self, record: ParsedRecord) -> NormalizedRecord:
        entity_name = _required_string(record.data, "entity_name")
        normalized_name = normalize_business_name(entity_name)
        normalized_data = compact_dict(
            {
                **record.data,
                "state": self.state,
                "normalized_name": normalized_name,
                "source_timestamp": parse_datetime(record.data.get("source_timestamp")),
                "source_id": record.source_id,
                "source_url": record.source_url,
                "captured_at": record.captured_at,
            }
        )
        return NormalizedRecord(
            record_type="business_entity",
            data=normalized_data,
            source_id=record.source_id,
            source_url=record.source_url,
            captured_at=record.captured_at,
            raw_artifact_path=record.raw_artifact_path,
            normalized_key=f"FL:BIZ:{normalized_name}",
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
        raise ValueError(f"Missing required Florida business entity field: {key}")
    return value.strip()
