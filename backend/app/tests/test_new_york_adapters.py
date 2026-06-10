from __future__ import annotations

import asyncio
from pathlib import Path
from shutil import copyfile

import pytest

from app.adapters import AdapterComplianceError
from app.adapters.new_york import (
    NewYorkUccAdapter,
    NyscefCaseDocumentsAdapter,
    NyscefNewCasesAdapter,
)
from app.services.ny_importer import build_mock_ny_signal_payloads

FIXTURES = Path(__file__).parent / "fixtures"


def test_nyscef_new_cases_mock_fetch_parse_normalize_saves_raw_artifact(tmp_path: Path) -> None:
    adapter = NyscefNewCasesAdapter(
        mode="mock",
        source_id="source-ny-cases",
        artifacts_dir=tmp_path,
        rate_limit_seconds=0,
    )

    artifacts = asyncio.run(adapter.fetch({"court_name": "Supreme Court, Kings County"}))
    parsed = asyncio.run(adapter.parse(artifacts[0]))
    normalized = asyncio.run(adapter.normalize(parsed[0]))

    assert len(artifacts) == 1
    assert Path(artifacts[0].storage_path).exists()
    assert artifacts[0].sha256_hash
    assert parsed[0].source_id == "source-ny-cases"
    assert parsed[0].source_url.startswith("https://iapps.courts.state.ny.us")
    assert normalized.record_type == "case"
    assert normalized.data["state"] == "NY"
    assert normalized.data["case_number"] == "501001/2026"
    assert normalized.data["source_id"] == "source-ny-cases"
    assert normalized.data["captured_at"] == artifacts[0].captured_at
    assert any(event.action == "raw_artifact_saved" for event in adapter.audit_events)


def test_manual_import_parses_requested_sample_fixtures(tmp_path: Path) -> None:
    cases_import_dir = tmp_path / "cases"
    docs_import_dir = tmp_path / "docs"
    ucc_import_dir = tmp_path / "ucc"
    cases_import_dir.mkdir()
    docs_import_dir.mkdir()
    ucc_import_dir.mkdir()
    copyfile(FIXTURES / "ny_nyscef_new_cases_sample.html", cases_import_dir / "sample.html")
    copyfile(FIXTURES / "ny_case_document_sample.txt", docs_import_dir / "sample.txt")
    copyfile(FIXTURES / "ny_ucc_search_sample.html", ucc_import_dir / "sample.html")

    cases_adapter = NyscefNewCasesAdapter(
        mode="manual_import",
        source_id="manual-cases",
        artifacts_dir=tmp_path / "artifacts",
        manual_import_dir=cases_import_dir,
        rate_limit_seconds=0,
    )
    docs_adapter = NyscefCaseDocumentsAdapter(
        mode="manual_import",
        source_id="manual-docs",
        artifacts_dir=tmp_path / "artifacts",
        manual_import_dir=docs_import_dir,
        rate_limit_seconds=0,
    )
    ucc_adapter = NewYorkUccAdapter(
        mode="manual_import",
        source_id="manual-ucc",
        artifacts_dir=tmp_path / "artifacts",
        manual_import_dir=ucc_import_dir,
        rate_limit_seconds=0,
    )

    case_artifact = asyncio.run(cases_adapter.fetch({}))[0]
    doc_artifact = asyncio.run(docs_adapter.fetch({}))[0]
    ucc_artifact = asyncio.run(ucc_adapter.fetch({}))[0]
    cases = asyncio.run(cases_adapter.parse(case_artifact))
    docs = asyncio.run(docs_adapter.parse(doc_artifact))
    uccs = asyncio.run(ucc_adapter.parse(ucc_artifact))

    assert len(cases) == 2
    assert cases[0].data["plaintiff_names"] == ["Yellowstone Capital LLC"]
    assert docs[0].data["document_type"] == "Complaint"
    assert "merchant cash advance" in docs[0].data["text_content"].lower()
    assert len(uccs) == 2
    assert uccs[1].data["secured_party_name"] == "Cloudfund LLC"


def test_live_mode_fails_closed_without_feature_flag(tmp_path: Path) -> None:
    adapter = NewYorkUccAdapter(
        mode="live_if_allowed",
        source_id="live-ucc",
        artifacts_dir=tmp_path,
        live_enabled=False,
        rate_limit_seconds=0,
    )

    with pytest.raises(AdapterComplianceError):
        asyncio.run(adapter.fetch({"debtor_name": "Bella Pizza LLC"}))

    assert adapter.audit_events[-1].action == "live_blocked"


def test_mock_ny_signal_payloads_create_at_least_twenty_classified_scored_signals(
    tmp_path: Path,
) -> None:
    payloads = asyncio.run(build_mock_ny_signal_payloads(artifacts_dir=tmp_path))

    assert len(payloads) >= 20
    assert all(payload.signal["state"] == "NY" for payload in payloads)
    assert all(payload.source_url.startswith("https://") for payload in payloads)
    assert all(payload.captured_at for payload in payloads)
    assert all(payload.source_id for payload in payloads)
    assert all(payload.signal["score"] > 0 for payload in payloads)
    assert all(payload.signal["grade"] in {"A_PLUS", "A", "B", "C", "D"} for payload in payloads)
    assert any(payload.score_result.keyword_classification.has_mca_core for payload in payloads)
    assert any(payload.score_result.funder_match.is_strong_match for payload in payloads)
