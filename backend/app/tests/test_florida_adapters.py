from __future__ import annotations

import asyncio
from pathlib import Path
from shutil import copyfile

import pytest

from app.adapters import AdapterComplianceError
from app.adapters.florida import (
    FloridaBusinessEntitiesAdapter,
    FloridaEfilingRecentCivilAdapter,
    FloridaUccAdapter,
)
from app.adapters.florida.fl_county_clerk_base import INITIAL_FLORIDA_COUNTY_CLERKS
from app.services.fl_importer import (
    build_mock_fl_business_entities,
    build_mock_fl_signal_payloads,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_florida_efiling_mock_excludes_restricted_records_and_normalizes(
    tmp_path: Path,
) -> None:
    adapter = FloridaEfilingRecentCivilAdapter(
        mode="mock",
        source_id="fl-civil-source",
        artifacts_dir=tmp_path,
        rate_limit_seconds=0,
    )

    artifacts = asyncio.run(adapter.fetch({"filing_date": "2026-06-09"}))
    parsed = asyncio.run(adapter.parse(artifacts[0]))
    normalized = asyncio.run(adapter.normalize(parsed[0]))

    assert len(parsed) == 12
    assert all(record.data["access_method"] == "mock" for record in parsed)
    assert all(record.data["source_timestamp"] for record in parsed)
    assert normalized.record_type == "case"
    assert normalized.data["state"] == "FL"
    assert normalized.data["source_id"] == "fl-civil-source"
    assert normalized.data["source_timestamp"].isoformat() == "2026-06-07T14:00:00+00:00"
    assert any(event.action == "record_excluded" for event in adapter.audit_events)


def test_florida_manual_import_parses_civil_ucc_and_business_fixtures(
    tmp_path: Path,
) -> None:
    civil_dir = tmp_path / "civil"
    ucc_dir = tmp_path / "ucc"
    business_dir = tmp_path / "business"
    civil_dir.mkdir()
    ucc_dir.mkdir()
    business_dir.mkdir()
    copyfile(FIXTURES / "fl_efiling_recent_civil_sample.html", civil_dir / "civil.html")
    copyfile(FIXTURES / "fl_ucc_search_sample.html", ucc_dir / "ucc.html")
    copyfile(FIXTURES / "fl_business_entities_sample.csv", business_dir / "business.csv")

    civil_adapter = FloridaEfilingRecentCivilAdapter(
        mode="manual_import",
        source_id="manual-fl-civil",
        artifacts_dir=tmp_path / "artifacts",
        manual_import_dir=civil_dir,
        rate_limit_seconds=0,
    )
    ucc_adapter = FloridaUccAdapter(
        mode="manual_import",
        source_id="manual-fl-ucc",
        artifacts_dir=tmp_path / "artifacts",
        manual_import_dir=ucc_dir,
        rate_limit_seconds=0,
    )
    business_adapter = FloridaBusinessEntitiesAdapter(
        mode="manual_import",
        source_id="manual-fl-business",
        artifacts_dir=tmp_path / "artifacts",
        manual_import_dir=business_dir,
        rate_limit_seconds=0,
    )

    civil_records = asyncio.run(civil_adapter.parse(asyncio.run(civil_adapter.fetch({}))[0]))
    ucc_records = asyncio.run(ucc_adapter.parse(asyncio.run(ucc_adapter.fetch({}))[0]))
    business_records = asyncio.run(
        business_adapter.parse(asyncio.run(business_adapter.fetch({}))[0])
    )
    normalized_business = asyncio.run(business_adapter.normalize(business_records[0]))

    assert len(civil_records) == 1
    assert civil_records[0].data["county"] == "Miami-Dade"
    assert civil_records[0].data["access_method"] == "manual_import"
    assert len(ucc_records) == 1
    assert ucc_records[0].data["filing_number"] == "FL202606010001"
    assert len(business_records) == 1
    assert normalized_business.data["normalized_name"] == "BISCAYNE BISTRO"


def test_florida_live_mode_fails_closed_without_feature_flag(tmp_path: Path) -> None:
    adapter = FloridaEfilingRecentCivilAdapter(
        mode="live_if_allowed",
        source_id="fl-live",
        artifacts_dir=tmp_path,
        live_enabled=False,
        rate_limit_seconds=0,
    )

    with pytest.raises(AdapterComplianceError):
        asyncio.run(adapter.fetch({"county": "Miami-Dade"}))

    assert adapter.audit_events[-1].action == "live_blocked"


def test_county_clerk_base_has_initial_county_configuration() -> None:
    counties = {config.county for config in INITIAL_FLORIDA_COUNTY_CLERKS}

    assert counties == {
        "Miami-Dade",
        "Broward",
        "Palm Beach",
        "Orange",
        "Hillsborough",
        "Pinellas",
        "Duval",
        "Polk",
        "Lee",
        "Collier",
        "Seminole",
        "Osceola",
    }
    assert all(config.search_strategy == "manual" for config in INITIAL_FLORIDA_COUNTY_CLERKS)


def test_mock_fl_signal_payloads_create_twenty_plus_enriched_scored_signals(
    tmp_path: Path,
) -> None:
    payloads = asyncio.run(build_mock_fl_signal_payloads(artifacts_dir=tmp_path))
    business_entities = asyncio.run(build_mock_fl_business_entities(artifacts_dir=tmp_path))

    assert len(payloads) >= 20
    assert len(business_entities) >= 12
    assert all(payload.signal["state"] == "FL" for payload in payloads)
    assert all(payload.source_url.startswith("https://") for payload in payloads)
    assert all(payload.signal["score"] > 0 for payload in payloads)
    assert all("business_enriched" in payload.signal["compliance_flags"] for payload in payloads)
    assert all("Sunbiz:" in str(payload.signal["summary"]) for payload in payloads)
    assert any(payload.score_result.keyword_classification.has_mca_core for payload in payloads)
    assert any(payload.score_result.funder_match.is_strong_match for payload in payloads)
