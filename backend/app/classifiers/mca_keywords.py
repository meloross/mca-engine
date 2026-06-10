from __future__ import annotations

import re
from dataclasses import dataclass

KEYWORD_GROUPS: dict[str, tuple[str, ...]] = {
    "mca_core": (
        "merchant cash advance",
        "MCA",
        "revenue purchase agreement",
        "future receivables",
        "receivables purchase agreement",
        "accounts receivable purchase transaction",
        "purchase and sale of future receivables",
        "purchased amount",
        "purchase price",
        "remittance",
    ),
    "payment_mechanics": (
        "daily ACH",
        "weekly ACH",
        "ACH debit",
        "reconciliation",
        "specified percentage",
        "lockbox",
        "blocked account",
        "payment processor",
    ),
    "legal_distress": (
        "confession of judgment",
        "COJ",
        "default judgment",
        "bank restraint",
        "UCC lien",
        "UCC-1",
        "personal guaranty",
        "fraudulent inducement",
        "criminal usury",
        "civil usury",
        "deceptive practices",
        "RICO",
        "breach of merchant agreement",
    ),
}

GROUP_WEIGHTS = {
    "mca_core": 0.55,
    "payment_mechanics": 0.20,
    "legal_distress": 0.25,
}


@dataclass(frozen=True)
class KeywordClassification:
    keyword_hits: tuple[str, ...]
    groups: dict[str, tuple[str, ...]]
    confidence_score: float
    text_length: int

    @property
    def has_mca_core(self) -> bool:
        return "mca_core" in self.groups

    @property
    def has_payment_mechanics(self) -> bool:
        return "payment_mechanics" in self.groups

    @property
    def has_legal_distress(self) -> bool:
        return "legal_distress" in self.groups


def classify_text(text: str | None) -> KeywordClassification:
    searchable = text or ""
    groups: dict[str, tuple[str, ...]] = {}
    hits: list[str] = []

    for group_name, keywords in KEYWORD_GROUPS.items():
        group_hits = tuple(keyword for keyword in keywords if _keyword_matches(keyword, searchable))
        if group_hits:
            groups[group_name] = group_hits
            hits.extend(group_hits)

    confidence = _confidence_score(groups)
    return KeywordClassification(
        keyword_hits=tuple(dict.fromkeys(hits)),
        groups=groups,
        confidence_score=confidence,
        text_length=len(searchable),
    )


def _keyword_matches(keyword: str, text: str) -> bool:
    return _keyword_pattern(keyword).search(text) is not None


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    if keyword == "UCC-1":
        return re.compile(r"\bUCC[-\s]?1\b", flags=re.IGNORECASE)

    escaped = re.escape(keyword)
    flexible_spaces = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![A-Z0-9]){flexible_spaces}(?![A-Z0-9])", flags=re.IGNORECASE)


def _confidence_score(groups: dict[str, tuple[str, ...]]) -> float:
    if not groups:
        return 0.0

    group_weight = sum(GROUP_WEIGHTS[group_name] for group_name in groups)
    extra_hits = max(0, sum(len(hits) for hits in groups.values()) - len(groups))
    extra_hit_bonus = min(0.10, extra_hits * 0.02)
    return round(min(1.0, group_weight + extra_hit_bonus), 4)
