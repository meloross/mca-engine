from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.dashboard import (
    _live_harvest_page,
    _signal_detail_page,
    _signals_page,
    _source_policies_page,
)
from app.api.signals import _filtered_signal_statement
from app.main import app
from app.services.presentation import redact_sensitive


def test_health_and_openapi_include_review_and_dashboard_routes() -> None:
    client = TestClient(app)

    health = client.get("/health")
    openapi = client.get("/openapi.json").json()

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert "/signals/{signal_id}/review" in openapi["paths"]
    assert "/signals/{signal_id}/deliver" in openapi["paths"]
    assert "/lead-form/mca-defense" in openapi["paths"]
    assert "/admin/form-leads/{form_lead_id}/route" in openapi["paths"]
    assert "/admin/sync/google-sheets/all" in openapi["paths"]
    assert "/admin/sync/google-sheets/status" in openapi["paths"]
    assert "/admin/sync/google-sheets/enrichment-log" in openapi["paths"]
    assert "/admin/jobs/status" in openapi["paths"]
    assert "/admin/jobs/recent" in openapi["paths"]
    assert "/admin/jobs/queues" in openapi["paths"]
    assert "/admin/jobs/enqueue/demo-leads" in openapi["paths"]
    assert "/admin/jobs/enqueue/enrichment" in openapi["paths"]
    assert "/admin/jobs/enqueue/enrichment-high-value" in openapi["paths"]
    assert "/admin/sources/policies" in openapi["paths"]
    assert "/admin/sources/policies/{source_code}/enable" in openapi["paths"]
    assert "/admin/live-harvest/start" in openapi["paths"]
    assert "/admin/live-harvest/status" in openapi["paths"]
    assert "/events/signals" in openapi["paths"]
    assert "/analytics/summary" in openapi["paths"]


def test_filtered_signal_statement_compiles_for_postgres() -> None:
    statement = _filtered_signal_statement(
        state="FL",
        county="Miami",
        grade="A_PLUS",
        min_score=75,
        signal_type="litigation_new_case",
        funder_name="Cloudfund",
        business_name="Bistro",
        date_from=None,
        date_to=None,
        status="new",
        has_document_text=True,
        enrichment_status="success",
        has_phone=True,
        has_email=True,
        has_owner_principal=True,
        has_website=True,
        min_enrichment_confidence=70,
        do_not_contact=False,
    )

    compiled = str(statement)

    assert "lead_signals" in compiled
    assert "case_documents" in compiled
    assert "score >=" in compiled
    assert "business_phone IS NOT NULL" in compiled
    assert "business_email IS NOT NULL" in compiled
    assert "owner_principal_name IS NOT NULL" in compiled
    assert "business_website IS NOT NULL" in compiled


def test_redact_sensitive_masks_identifiers() -> None:
    text = "SSN 123-45-6789 account 123456789012 DOB 01/02/1970"

    assert redact_sensitive(text) == "SSN [REDACTED] account [REDACTED] DOB [REDACTED]"


def test_dashboard_signals_page_has_filters_and_a_plus_link() -> None:
    html = _signals_page(
        [
            {
                "id": "signal-1",
                "lead_reference_id": "MCA-FL-20260610-000001",
                "batch_number": "BATCH-FL-20260610-001",
                "business_name": "Biscayne Bistro LLC",
                "state": "FL",
                "county": "Miami-Dade",
                "grade": "A_PLUS",
                "score": 95,
                "funder_name": "Cloudfund",
                "signal_type": "litigation_new_case",
                "status": "new",
                "signal_date": "2026-06-07",
                "source_name": "FL Demo Source",
                "source_url": "https://example.test/source",
                "source_captured_at": "2026-06-10T00:00:00+00:00",
                "master_sheet_sync_status": "not_synced",
                "exported_to_master_sheet": False,
                "master_sheet_synced_at": None,
            }
        ],
        {"state": "FL", "grade": "A_PLUS"},
    )

    assert "/dashboard?grade=A_PLUS" in html
    assert "Biscayne Bistro LLC" in html
    assert 'name="state"' in html


def test_dashboard_signal_detail_contains_review_delivery_and_explanation() -> None:
    html = _signal_detail_page(
        {
            "id": "signal-1",
            "lead_reference_id": "MCA-FL-20260610-000001",
            "batch_number": "BATCH-FL-20260610-001",
            "business_name": "Biscayne Bistro LLC",
            "title": "New FL MCA litigation signal",
            "grade": "A_PLUS",
            "score": 95,
            "source_url": "https://example.test/source",
            "case": None,
            "ucc_filing": None,
            "keyword_hits": ["merchant cash advance"],
            "score_reasons": ["+30 known MCA funder match"],
            "compliance_flags": ["business_enriched"],
        },
        [{"id": "buyer-1", "firm_name": "MCA Counsel LLP"}],
    )

    assert "reviewSignal('reviewed')" in html
    assert "deliverSignal()" in html
    assert "merchant cash advance" in html
    assert "+30 known MCA funder match" in html


def test_dashboard_source_policy_page_has_policy_actions() -> None:
    html = _source_policies_page(
        [
            {
                "source_code": "FL_SUNBIZ_DOWNLOADS",
                "source_name": "Florida Division of Corporations Data Downloads",
                "state": "FL",
                "acquisition_method": "official_download",
                "status": "active",
                "automation_allowed": True,
                "live_enabled": True,
                "rate_limit_seconds": 2,
                "status_reason": "Official public data download.",
            }
        ]
    )

    assert "FL_SUNBIZ_DOWNLOADS" in html
    assert "sourcePolicyAction('FL_SUNBIZ_DOWNLOADS', 'enable')" in html
    assert "/dashboard/live-harvest" in html


def test_dashboard_live_harvest_page_posts_admin_endpoint() -> None:
    html = _live_harvest_page()

    assert "/admin/live-harvest/start?" in html
    assert "state-ny" in html
    assert "state-fl" in html
