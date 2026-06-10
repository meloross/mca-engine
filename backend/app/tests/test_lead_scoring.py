from __future__ import annotations

from datetime import date

from app.scoring.lead_score import compliance_exclude, score_signal


def test_score_signal_grades_high_value_new_litigation_signal() -> None:
    record = {
        "signal_type": "litigation_new_case",
        "caption": "Yellowstone Capital LLC v. Bella Pizza LLC and Maria Gomez",
        "plaintiff_names": ["Yellowstone Capital LLC"],
        "defendant_names": ["Bella Pizza LLC", "Maria Gomez"],
        "document_text": (
            "Complaint for breach of merchant agreement arising from a revenue purchase "
            "agreement, purchased amount, daily ACH debit, and confession of judgment."
        ),
        "filing_date": date(2026, 6, 7),
        "defense_attorney_names": [],
        "source_automation_allowed": True,
    }

    result = score_signal(record, as_of=date(2026, 6, 9))

    assert result.score == 110
    assert result.grade == "A_PLUS"
    assert result.risk_score == 15
    assert result.funder_match.matched_funder == "Yellowstone Capital"
    assert result.keyword_classification.has_mca_core
    assert "+10 no defense attorney detected" in result.reasons


def test_score_signal_scores_ucc_signal_with_multiple_filings() -> None:
    record = {
        "signal_type": "ucc_initial",
        "ucc_secured_party": "Cloudfund LLC",
        "debtor_name": "Hudson Deli Group LLC",
        "defendant_names": ["Hudson Deli Group LLC"],
        "ucc_collateral_text": (
            "All future receivables, payment processor rights, lockbox proceeds, "
            "and accounts receivable purchase transaction collateral."
        ),
        "signal_date": "2026-06-05",
        "multiple_ucc_filings_count": 3,
        "source_automation_allowed": True,
    }

    result = score_signal(record, as_of=date(2026, 6, 9))

    assert result.score == 95
    assert result.grade == "A_PLUS"
    assert result.risk_score == 10
    assert result.funder_match.matched_funder == "Cloudfund"
    assert "+10 multiple UCC filings for same business" in result.reasons


def test_compliance_exclude_and_penalties_force_exclude_grade() -> None:
    record = {
        "caption": "WCM Funding LLC v. Restricted Merchant LLC",
        "plaintiff_names": ["WCM Funding LLC"],
        "defendant_names": ["Restricted Merchant LLC"],
        "document_text": "Merchant cash advance default judgment.",
        "filing_date": date(2026, 6, 8),
        "sealed": True,
        "source_automation_allowed": False,
    }

    decision = compliance_exclude(record)
    result = score_signal(record, as_of=date(2026, 6, 9))

    assert decision.excluded
    assert decision.reasons == (
        "confidential/sealed/restricted record",
        "source disallows automation or use",
    )
    assert result.excluded
    assert result.grade == "EXCLUDE"
    assert result.score == -50
    assert result.risk_score == 165


def test_score_signal_penalizes_weak_match_and_stale_record() -> None:
    record = {
        "caption": "Fast Cash Merchant Advance v. Old Town Market LLC",
        "plaintiff_names": ["Fast Cash Merchant Advance"],
        "defendant_names": ["Old Town Market LLC"],
        "document_text": "Alleged purchase price and remittance dispute.",
        "filing_date": date(2025, 1, 1),
        "source_automation_allowed": True,
    }

    result = score_signal(record, as_of=date(2026, 6, 9))

    assert result.funder_match.is_weak_match
    assert result.score == -25
    assert result.grade == "EXCLUDE"
    assert "-30 weak entity match: Fast Cash Advance" in result.reasons
    assert "-25 stale record over 180 days" in result.reasons


def test_score_signal_bankruptcy_mca_creditor_bonus() -> None:
    record = {
        "signal_type": "bankruptcy_mca_creditor",
        "creditor_name": "Fundry",
        "document_text": "Schedule E/F lists merchant cash advance claim.",
        "signal_date": date(2026, 6, 9),
        "source_automation_allowed": True,
    }

    result = score_signal(record, as_of=date(2026, 6, 9))

    assert result.score == 85
    assert result.grade == "A"
    assert "+10 bankruptcy/MCA creditor match" in result.reasons
