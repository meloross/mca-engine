from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models import BuyerAccount, BuyerRule, FormLead, LeadSignalGrade
from app.scoring.form_lead_score import score_form_lead
from app.services.form_leads import (
    DEFAULT_LEAD_FORM_DISCLAIMER,
    FORM_LEAD_SIGNAL_TYPE,
    buyer_rule_matches_form_lead,
    serialize_form_lead,
)


def test_mca_defense_form_lead_scores_urgent_known_funder() -> None:
    result = score_form_lead(
        {
            "has_been_sued": True,
            "bank_account_frozen": True,
            "court_deadline_date": date(2026, 6, 15),
            "ucc_lien_issue": True,
            "total_mca_balance_range": "$50k-$100k",
            "mca_funder_names": ["Cloudfund LLC"],
            "has_attorney": False,
            "consent_to_contact": True,
        },
        as_of=date(2026, 6, 10),
    )

    assert result.score == 115
    assert result.grade == "A_PLUS"
    assert not result.excluded
    assert "+10 known MCA funder: Cloudfund" in result.reasons


def test_mca_defense_form_lead_without_consent_is_excluded() -> None:
    result = score_form_lead(
        {
            "has_been_sued": True,
            "bank_account_frozen": True,
            "court_deadline_date": date(2026, 6, 12),
            "ucc_lien_issue": True,
            "total_mca_balance_range": "over $50k",
            "mca_funder_names": ["Yellowstone Capital"],
            "has_attorney": False,
            "consent_to_contact": False,
        },
        as_of=date(2026, 6, 10),
    )

    assert result.score == 15
    assert result.grade == "EXCLUDE"
    assert result.excluded
    assert "no express consent to contact" in result.exclusion_reasons


def test_buyer_rule_matches_form_lead_by_state_county_score_and_type() -> None:
    buyer = BuyerAccount(
        firm_name="MCA Defense LLP",
        email="routing@example.test",
        states=["FL"],
        counties=["Miami-Dade"],
        practice_tags=["mca_defense"],
        active=True,
    )
    rule = BuyerRule(
        buyer_account=buyer,
        state="FL",
        counties=["Miami-Dade"],
        min_score=75,
        signal_types=[FORM_LEAD_SIGNAL_TYPE],
        active=True,
    )
    form_lead = _form_lead(score=85, state="FL", case_county="Miami-Dade")

    assert buyer_rule_matches_form_lead(rule, form_lead)


def test_buyer_rule_rejects_no_consent_excluded_form_lead_score() -> None:
    buyer = BuyerAccount(
        firm_name="MCA Defense LLP",
        email="routing@example.test",
        states=["NY"],
        counties=[],
        practice_tags=["mca_defense"],
        active=True,
    )
    rule = BuyerRule(
        buyer_account=buyer,
        state="NY",
        counties=[],
        min_score=1,
        signal_types=[FORM_LEAD_SIGNAL_TYPE],
        active=True,
    )
    form_lead = _form_lead(
        score=-70,
        grade=LeadSignalGrade.EXCLUDE,
        state="NY",
        consent_to_contact=False,
    )

    assert not buyer_rule_matches_form_lead(rule, form_lead)


def test_form_lead_serializer_includes_consent_and_disclaimer_detail() -> None:
    form_lead = _form_lead(
        score=85,
        state="FL",
        case_county="Orange",
        consent_to_contact=True,
        consent_text="I agree to be contacted about my MCA defense request.",
    )

    payload = serialize_form_lead(form_lead, include_detail=True)

    assert payload["consent_to_contact"] is True
    assert payload["consent_text"] == "I agree to be contacted about my MCA defense request."
    assert payload["disclaimer_text"] == DEFAULT_LEAD_FORM_DISCLAIMER


def _form_lead(
    *,
    score: int,
    state: str,
    case_county: str | None = None,
    grade: LeadSignalGrade = LeadSignalGrade.A,
    consent_to_contact: bool = True,
    consent_text: str = "I consent to contact.",
) -> FormLead:
    return FormLead(
        form_lead_ref_id="FORM-MCA-20260610-000001",
        batch_number="BATCH-FORM-20260610-001",
        state=state,
        business_name="Biscayne Bistro LLC",
        contact_name="Avery Rivera",
        email="avery@example.test",
        phone="555-0100",
        preferred_contact_method="email",
        legal_issue_type="mca_defense",
        has_been_sued=True,
        case_state=state,
        case_county=case_county,
        case_number="2026-CA-100",
        mca_funder_names=["Cloudfund"],
        daily_weekly_payment_amount=Decimal("1500.00"),
        total_mca_balance_range="$50k-$100k",
        bank_account_frozen=True,
        ucc_lien_issue=True,
        court_deadline_date=date(2026, 6, 15),
        has_attorney=False,
        consent_to_contact=consent_to_contact,
        consent_text=consent_text,
        disclaimer_text=DEFAULT_LEAD_FORM_DISCLAIMER,
        page_url="https://example.test/mca-defense",
        ip_hash="0" * 64,
        user_agent="pytest",
        source_campaign="test",
        score=score,
        grade=grade,
        status="new" if consent_to_contact else "excluded",
    )
