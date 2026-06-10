from __future__ import annotations

from app.compliance import normalize_business_name


def name_match_confidence(query_name: str, candidate_name: str) -> int:
    query = _safe_normalize(query_name)
    candidate = _safe_normalize(candidate_name)
    if not query or not candidate:
        return 0
    if query == candidate:
        return 95
    if query in candidate or candidate in query:
        return 82
    query_tokens = set(query.split())
    candidate_tokens = set(candidate.split())
    if not query_tokens or not candidate_tokens:
        return 0
    overlap = len(query_tokens & candidate_tokens) / len(query_tokens | candidate_tokens)
    return int(overlap * 75)


def combine_confidences(values: list[int]) -> int:
    if not values:
        return 0
    return max(0, min(100, round(sum(values) / len(values))))


def _safe_normalize(value: str) -> str:
    try:
        return normalize_business_name(value)
    except ValueError:
        return ""
