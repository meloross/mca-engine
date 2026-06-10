from __future__ import annotations

from app.classifiers.funder_matcher import SEED_MCA_FUNDERS, match_funder
from app.classifiers.mca_keywords import classify_text


def test_classify_text_detects_mca_core_payment_and_distress_terms() -> None:
    result = classify_text(
        """
        Plaintiff alleges breach of a revenue purchase agreement involving future
        receivables. The merchant was subject to daily ACH debit remittances and
        a bank restraint after entry of a confession of judgment.
        """
    )

    assert "revenue purchase agreement" in result.keyword_hits
    assert "daily ACH" in result.groups["payment_mechanics"]
    assert "confession of judgment" in result.groups["legal_distress"]
    assert result.has_mca_core
    assert result.has_payment_mechanics
    assert result.has_legal_distress
    assert result.confidence_score >= 0.90


def test_classify_text_handles_acronyms_without_substring_false_positive() -> None:
    result = classify_text("The MCA agreement references a UCC 1 lien and COJ.")
    false_positive = classify_text("The mechanical equipment purchase order was disputed.")

    assert "MCA" in result.keyword_hits
    assert "UCC-1" in result.keyword_hits
    assert "COJ" in result.keyword_hits
    assert false_positive.keyword_hits == ()
    assert false_positive.confidence_score == 0.0


def test_match_funder_exact_alias_and_fuzzy_matches() -> None:
    exact = match_funder("Yellowstone Capital LLC")
    alias = match_funder("Cloud Fund")
    fuzzy = match_funder("Midnight Advance Capita")

    assert "Cloudfund" in SEED_MCA_FUNDERS
    assert exact.matched_funder == "Yellowstone Capital"
    assert exact.confidence == 1.0
    assert alias.matched_funder == "Cloudfund"
    assert alias.alias_match
    assert fuzzy.matched_funder == "Midnight Advance Capital"
    assert 0.68 <= fuzzy.confidence < 1.0


def test_match_funder_returns_no_match_for_unrelated_party() -> None:
    result = match_funder("Acme Restaurant Holdings LLC")

    assert result.matched_funder is None
    assert result.confidence == 0.0
