from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.classifiers.funder_matcher import FunderMatch, match_funder

Record = Mapping[str, Any] | object


@dataclass(frozen=True)
class FormLeadScoreResult:
    score: int
    grade: str
    reasons: tuple[str, ...]
    excluded: bool
    exclusion_reasons: tuple[str, ...]
    funder_match: FunderMatch


def score_form_lead(record: Record, *, as_of: date | None = None) -> FormLeadScoreResult:
    as_of_date = as_of or date.today()
    score = 0
    reasons: list[str] = []
    exclusion_reasons: list[str] = []
    funder_match = _best_funder_match(record)

    if _is_true(record, "has_been_sued"):
        score += 30
        reasons.append("+30 sued already")

    if _is_true(record, "bank_account_frozen"):
        score += 25
        reasons.append("+25 bank account frozen or restrained")

    deadline = _coerce_date(_get(record, "court_deadline_date"))
    if deadline is not None and 0 <= (deadline - as_of_date).days <= 14:
        score += 20
        reasons.append("+20 court deadline within 14 days")

    if _is_true(record, "ucc_lien_issue"):
        score += 15
        reasons.append("+15 UCC lien issue")

    if _balance_over_50k(_get(record, "total_mca_balance_range")):
        score += 15
        reasons.append("+15 total MCA balance over $50k")

    if funder_match.is_strong_match:
        score += 10
        reasons.append(f"+10 known MCA funder: {funder_match.matched_funder}")

    if _is_true(record, "has_attorney"):
        score -= 50
        reasons.append("-50 already has attorney")

    if not _is_true(record, "consent_to_contact"):
        score -= 100
        reasons.append("-100 no express consent to contact")
        exclusion_reasons.append("no express consent to contact")

    excluded = bool(exclusion_reasons)
    grade = _grade(score, excluded=excluded)
    return FormLeadScoreResult(
        score=score,
        grade=grade,
        reasons=tuple(reasons),
        excluded=excluded,
        exclusion_reasons=tuple(exclusion_reasons),
        funder_match=funder_match,
    )


def _best_funder_match(record: Record) -> FunderMatch:
    best = match_funder(None)
    for value in _sequence_string_items(_get(record, "mca_funder_names")):
        candidate = match_funder(value)
        if candidate.confidence > best.confidence:
            best = candidate
    return best


def _balance_over_50k(value: object | None) -> bool:
    if value is None:
        return False
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value)) > Decimal("50000")
    if not isinstance(value, str):
        return False

    lowered = value.lower()
    if any(token in lowered for token in ("over 50", ">50", "50k+", "over $50", "above 50")):
        return True

    numbers = [int(match.replace(",", "")) for match in re.findall(r"\d[\d,]*", lowered)]
    if "k" in lowered:
        numbers = [number * 1000 for number in numbers]
    return any(number > 50_000 for number in numbers)


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


def _get(record: Record, key: str) -> object | None:
    if isinstance(record, Mapping):
        return record.get(key)
    return getattr(record, key, None)


def _is_true(record: Record, key: str) -> bool:
    return _get(record, key) is True


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


def _sequence_values(value: object | None) -> tuple[object, ...]:
    if value is None or isinstance(value, str):
        return ()
    if isinstance(value, Sequence):
        return tuple(value)
    return ()


def _sequence_string_items(value: object | None) -> tuple[str, ...]:
    return tuple(item for item in _sequence_values(value) if isinstance(item, str))
