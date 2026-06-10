from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.classifiers.funder_matcher import FunderMatch, match_funder
from app.classifiers.mca_keywords import KeywordClassification, classify_text

Record = Mapping[str, Any] | object


@dataclass(frozen=True)
class ComplianceDecision:
    excluded: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class LeadScoreResult:
    score: int
    risk_score: int
    grade: str
    reasons: tuple[str, ...]
    excluded: bool
    exclusion_reasons: tuple[str, ...]
    keyword_classification: KeywordClassification
    funder_match: FunderMatch


def compliance_exclude(record: Record) -> ComplianceDecision:
    reasons: list[str] = []

    if _has_any_flag(record, ("confidential", "sealed", "restricted")):
        reasons.append("confidential/sealed/restricted record")

    source_disallowed = _is_false(
        record,
        "source_automation_allowed",
        "automation_allowed",
        "source_allows_use",
    )
    terms_disallowed = _is_true(
        record,
        "terms_prohibit_automation",
        "terms_prohibit_use",
        "source_disallows_use",
    )
    if source_disallowed or terms_disallowed or "source_disallows_use" in _string_flags(record):
        reasons.append("source disallows automation or use")

    if _is_true(record, "suppressed") or "suppressed" in _string_flags(record):
        reasons.append("suppressed by suppression list")

    return ComplianceDecision(excluded=bool(reasons), reasons=tuple(dict.fromkeys(reasons)))


def score_signal(record: Record, *, as_of: date | None = None) -> LeadScoreResult:
    as_of_date = as_of or date.today()
    keyword_classification = classify_text(_combined_text(record))
    funder_match = _best_funder_match(record)
    compliance = compliance_exclude(record)

    score = 0
    risk_score = 0
    reasons: list[str] = []

    if funder_match.is_strong_match:
        score += 30
        reasons.append(f"+30 known MCA funder match: {funder_match.matched_funder}")
    elif funder_match.is_weak_match:
        score -= 30
        risk_score += 30
        reasons.append(f"-30 weak entity match: {funder_match.matched_funder}")

    signal_date = _record_date(record)
    if signal_date and 0 <= (as_of_date - signal_date).days <= 7:
        score += 25
        reasons.append("+25 new case or signal filed within 7 days")

    if keyword_classification.has_mca_core:
        score += 20
        reasons.append("+20 complaint/document has MCA core keyword")

    if keyword_classification.has_legal_distress:
        score += 15
        risk_score += 15
        reasons.append("+15 legal distress keyword")

    if _merchant_business_defendant_detected(record):
        score += 10
        reasons.append("+10 merchant/business defendant detected")

    if _no_defense_attorney_detected(record):
        score += 10
        reasons.append("+10 no defense attorney detected")

    if _integer_value(record, "multiple_ucc_filings_count", "ucc_filing_count") > 1:
        score += 10
        risk_score += 10
        reasons.append("+10 multiple UCC filings for same business")

    if _bankruptcy_mca_creditor_match(record, funder_match):
        score += 10
        risk_score += 10
        reasons.append("+10 bankruptcy/MCA creditor match")

    if "confidential/sealed/restricted record" in compliance.reasons:
        score -= 100
        risk_score += 100
        reasons.append("-100 confidential/sealed/restricted flag")

    if "source disallows automation or use" in compliance.reasons:
        score -= 50
        risk_score += 50
        reasons.append("-50 source disallows automation or use")

    if signal_date and (as_of_date - signal_date).days > 180:
        score -= 25
        risk_score += 25
        reasons.append("-25 stale record over 180 days")

    grade = _grade(score, excluded=compliance.excluded)
    return LeadScoreResult(
        score=score,
        risk_score=risk_score,
        grade=grade,
        reasons=tuple(reasons),
        excluded=compliance.excluded,
        exclusion_reasons=compliance.reasons,
        keyword_classification=keyword_classification,
        funder_match=funder_match,
    )


def _combined_text(record: Record) -> str:
    fields = (
        "case_caption",
        "caption",
        "document_text",
        "text_content",
        "ucc_secured_party",
        "secured_party_name",
        "ucc_collateral_text",
        "collateral_text",
        "summary",
    )
    values = [_string_value(_get(record, field)) for field in fields]
    values.extend(_joined_sequence_strings(_get(record, field)) for field in ("party_names",))
    values.extend(
        _joined_sequence_strings(_get(record, field))
        for field in ("plaintiff_names", "defendant_names", "attorney_names")
    )
    return "\n".join(value for value in values if value)


def _best_funder_match(record: Record) -> FunderMatch:
    candidates = (
        "funder_name",
        "ucc_secured_party",
        "secured_party_name",
        "creditor_name",
        "plaintiff_name",
    )
    best = match_funder(None)
    for field in candidates:
        value = _get(record, field)
        if isinstance(value, str):
            candidate = match_funder(value)
            if candidate.confidence > best.confidence:
                best = candidate

    for value in _sequence_values(_get(record, "plaintiff_names")):
        if isinstance(value, str):
            candidate = match_funder(value)
            if candidate.confidence > best.confidence:
                best = candidate

    return best


def _merchant_business_defendant_detected(record: Record) -> bool:
    if _is_true(record, "merchant_business_defendant", "business_defendant"):
        return True

    defendant_names = _sequence_string_items(_get(record, "defendant_names"))
    if not defendant_names:
        return False

    business_terms = (
        "LLC",
        "INC",
        "CORP",
        "COMPANY",
        "CO.",
        "LTD",
        "PLLC",
        "D/B/A",
        "DBA",
        "RESTAURANT",
        "DELI",
        "PIZZA",
        "MARKET",
        "MERCHANT",
    )
    return any(any(term in name.upper() for term in business_terms) for name in defendant_names)


def _no_defense_attorney_detected(record: Record) -> bool:
    if _is_true(record, "no_defense_attorney"):
        return True
    if _is_false(record, "has_defense_attorney"):
        return True

    for field in ("defense_attorney_names", "defendant_attorney_names"):
        value = _get(record, field)
        if value is not None and not _sequence_string_items(value):
            return True

    return False


def _bankruptcy_mca_creditor_match(record: Record, funder_match: FunderMatch) -> bool:
    signal_type = _string_value(_get(record, "signal_type")).lower()
    return bool(funder_match.is_strong_match) and (
        _is_true(record, "bankruptcy", "is_bankruptcy") or signal_type == "bankruptcy_mca_creditor"
    )


def _record_date(record: Record) -> date | None:
    for field in ("signal_date", "filing_date", "case_filing_date", "record_date"):
        coerced = _coerce_date(_get(record, field))
        if coerced is not None:
            return coerced
    return None


def _grade(score: int, *, excluded: bool) -> str:
    if excluded or score <= 0:
        return "EXCLUDE"
    if score >= 90:
        return "A_PLUS"
    if score >= 75:
        return "A"
    if score >= 55:
        return "B"
    if score >= 35:
        return "C"
    return "D"


def _has_any_flag(record: Record, flag_names: Sequence[str]) -> bool:
    flag_values = _string_flags(record)
    return any(_is_true(record, flag, f"is_{flag}") or flag in flag_values for flag in flag_names)


def _string_flags(record: Record) -> set[str]:
    flags: set[str] = set()
    for field in ("flags", "compliance_flags", "source_flags"):
        flags.update(value.lower() for value in _sequence_string_items(_get(record, field)))
    return flags


def _get(record: Record, key: str) -> object | None:
    if isinstance(record, Mapping):
        return record.get(key)
    return getattr(record, key, None)


def _is_true(record: Record, *keys: str) -> bool:
    return any(_get(record, key) is True for key in keys)


def _is_false(record: Record, *keys: str) -> bool:
    return any(_get(record, key) is False for key in keys)


def _integer_value(record: Record, *keys: str) -> int:
    for key in keys:
        value = _get(record, key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _coerce_date(value: object | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _string_value(value: object | None) -> str:
    return value if isinstance(value, str) else ""


def _sequence_values(value: object | None) -> tuple[object, ...]:
    if value is None or isinstance(value, str):
        return ()
    if isinstance(value, Sequence):
        return tuple(value)
    return ()


def _sequence_string_items(value: object | None) -> tuple[str, ...]:
    return tuple(item for item in _sequence_values(value) if isinstance(item, str))


def _joined_sequence_strings(value: object | None) -> str:
    return " ".join(_sequence_string_items(value))
