from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.dashboard import _signal_detail_page, _signals_page
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
    )

    compiled = str(statement)

    assert "lead_signals" in compiled
    assert "case_documents" in compiled
    assert "score >=" in compiled


def test_redact_sensitive_masks_identifiers() -> None:
    text = "SSN 123-45-6789 account 123456789012 DOB 01/02/1970"

    assert redact_sensitive(text) == "SSN [REDACTED] account [REDACTED] DOB [REDACTED]"


def test_dashboard_signals_page_has_filters_and_a_plus_link() -> None:
    html = _signals_page(
        [
            {
                "id": "signal-1",
                "business_name": "Biscayne Bistro LLC",
                "state": "FL",
                "county": "Miami-Dade",
                "grade": "A_PLUS",
                "score": 95,
                "funder_name": "Cloudfund",
                "signal_type": "litigation_new_case",
                "status": "new",
                "signal_date": "2026-06-07",
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
