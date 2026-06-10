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
from app.adapters.new_york.mock_data import render_case_document_text
from app.adapters.new_york.parsing import compact_dict, parse_datetime

NYSCEF_CASE_DOCUMENTS_URL = (
    "https://www.nycourts.gov/help/representing-yourself-court/"
    "getting-court-records-case-information"
)


class NyscefCaseDocumentsAdapter(SourceAdapter):
    source_name = "NYSCEF Case Documents Guest Search"
    state = "NY"
    base_url = NYSCEF_CASE_DOCUMENTS_URL
    terms_notes = (
        "Manual/import-first document adapter for guest-accessible records. Live access is "
        "disabled unless terms and court controls permit automation."
    )
    automation_allowed = None

    async def fetch(self, params: dict[str, Any]) -> list[RawArtifact]:
        if self.mode == "mock":
            text = render_case_document_text()
            return [
                self.save_raw_artifact(
                    content=text,
                    artifact_type="txt",
                    source_url=self.base_url,
                    filename_hint="ny_case_document_mock",
                    metadata={"params": params, "access_method": "mock"},
                )
            ]

        if self.mode == "manual_import":
            artifacts: list[RawArtifact] = []
            for path in self.manual_files(suffixes=(".txt", ".pdf")):
                artifacts.append(self._save_manual_file(path, params=params))
            return artifacts

        self.assert_live_allowed()
        raise NotImplementedError("NYSCEF document live access is disabled until terms allow it.")

    async def parse(self, artifact: RawArtifact) -> list[ParsedRecord]:
        text = (
            _read_pdf_text(artifact.storage_path)
            if artifact.artifact_type == "pdf"
            else artifact.read_text()
        )
        parsed_data = _parse_document_text(text)
        document_url = parsed_data.get("document_url") or artifact.source_url
        record = ParsedRecord(
            record_type="case_document",
            data={**parsed_data, "document_url": document_url, "source_url": document_url},
            source_id=artifact.source_id,
            source_url=document_url,
            captured_at=artifact.captured_at,
            raw_artifact_path=artifact.storage_path,
        )
        self.audit("parsed", "Parsed NYSCEF case document artifact.", count=1)
        return [record]

    async def normalize(self, record: ParsedRecord) -> NormalizedRecord:
        title = str(record.data.get("document_title") or "document").strip()
        filed_at = parse_datetime(record.data.get("filed_at"))
        normalized_data = compact_dict(
            {
                **record.data,
                "state": self.state,
                "filed_at": filed_at,
                "source_id": record.source_id,
                "source_url": record.source_url,
                "captured_at": record.captured_at,
            }
        )
        return NormalizedRecord(
            record_type="case_document",
            data=normalized_data,
            source_id=record.source_id,
            source_url=record.source_url,
            captured_at=record.captured_at,
            raw_artifact_path=record.raw_artifact_path,
            normalized_key=f"NY:DOC:{title.upper()}:{record.captured_at.isoformat()}",
        )

    def _save_manual_file(self, path: Path, *, params: dict[str, Any]) -> RawArtifact:
        artifact_type: AdapterArtifactType = "pdf" if path.suffix.lower() == ".pdf" else "txt"
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


def _parse_document_text(text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    body_lines: list[str] = []
    in_body = False
    key_map = {
        "document title": "document_title",
        "document type": "document_type",
        "filed at": "filed_at",
        "document url": "document_url",
    }
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower() == "text:":
            in_body = True
            continue
        if not in_body and ":" in stripped:
            key, value = stripped.split(":", 1)
            normalized_key = key_map.get(key.strip().lower())
            if normalized_key:
                metadata[normalized_key] = value.strip()
                continue
        if stripped:
            body_lines.append(stripped)

    metadata["text_content"] = "\n".join(body_lines)
    return metadata


def _read_pdf_text(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)
