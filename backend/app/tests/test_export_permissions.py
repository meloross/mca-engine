from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

from sqlalchemy.orm import Session

from app.exports.lead_exporter import form_leads_to_export_rows
from app.exports.permissions import NO_CONSENT_REDACTED
from app.models import FormLead, LeadSignalGrade


def test_opt_in_no_consent_redacts_contact_fields() -> None:
    form_lead = FormLead(
        id=uuid4(),
        form_lead_ref_id="FORM-MCA-20260610-000001",
        batch_number="BATCH-FORM-20260610-001",
        state="NY",
        business_name="Demo No Consent Merchant LLC",
        contact_name="Demo Contact",
        email="demo-no-consent@example.com",
        phone="555-0199",
        preferred_contact_method="email",
        legal_issue_type="mca_defense",
        has_been_sued=True,
        case_state="NY",
        case_county="Kings",
        case_number="DEMO-NO-CONSENT-001",
        mca_funder_names=["Cloudfund"],
        daily_weekly_payment_amount=Decimal("1500.00"),
        total_mca_balance_range="over $50k",
        bank_account_frozen=True,
        ucc_lien_issue=True,
        court_deadline_date=date(2026, 6, 15),
        has_attorney=False,
        consent_to_contact=False,
        consent_text="I did not consent.",
        disclaimer_text="No legal advice.",
        page_url="https://demo.local/lead-form/mca-defense",
        ip_hash="0" * 64,
        user_agent="pytest",
        source_campaign="test",
        score=0,
        grade=LeadSignalGrade.EXCLUDE,
        status="excluded",
        created_at=datetime(2026, 6, 10, tzinfo=UTC),
    )

    rows = form_leads_to_export_rows(cast(Session, _NoConsentSession()), [form_lead])

    assert rows[0]["contact_name"] == NO_CONSENT_REDACTED
    assert rows[0]["email"] == NO_CONSENT_REDACTED
    assert rows[0]["phone"] == NO_CONSENT_REDACTED
    assert rows[0]["consent_text"] == NO_CONSENT_REDACTED


class _NoConsentSession:
    def scalar(self, statement: object) -> object | None:
        return None
