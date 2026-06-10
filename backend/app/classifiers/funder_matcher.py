from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.compliance import normalize_funder_name

SEED_MCA_FUNDERS: tuple[str, ...] = (
    "Yellowstone Capital",
    "ABC Merchant Solutions",
    "Advance Merchant Services",
    "Business Advance Team",
    "Capital Advance Services",
    "Capital Merchant Services",
    "Cash Village Funding",
    "Fast Cash Advance",
    "Fundry",
    "Fundzio",
    "Green Capital Funding",
    "HFH Merchant Services",
    "High Speed Capital",
    "Merchant Capital Pay",
    "Merchant Funding Services",
    "Midnight Advance Capital",
    "Thryve Capital Funding",
    "WCM Funding",
    "World Global Capital",
    "Delta Bridge Funding",
    "Cloudfund",
)

DEFAULT_ALIASES: dict[str, tuple[str, ...]] = {
    "Yellowstone Capital": ("Yellowstone Capital LLC", "Yellowstone"),
    "ABC Merchant Solutions": ("ABC Merchant Solutions LLC", "ABC Merchant"),
    "Advance Merchant Services": ("Advance Merchant Services LLC",),
    "Cloudfund": ("Cloudfund LLC", "Cloud Fund"),
    "WCM Funding": ("WCM Funding LLC",),
}


@dataclass(frozen=True)
class FunderMatch:
    matched_funder: str | None
    confidence: float
    alias_match: bool
    matched_alias: str | None
    normalized_query: str

    @property
    def is_match(self) -> bool:
        return self.matched_funder is not None

    @property
    def is_strong_match(self) -> bool:
        return self.confidence >= 0.85

    @property
    def is_weak_match(self) -> bool:
        return self.matched_funder is not None and self.confidence < 0.85


def match_funder(
    name: str | None,
    funders: Sequence[str] | Mapping[str, Sequence[str]] | None = None,
) -> FunderMatch:
    normalized_query = normalize_funder_name(name) if name and name.strip() else ""
    if not normalized_query:
        return FunderMatch(
            matched_funder=None,
            confidence=0.0,
            alias_match=False,
            matched_alias=None,
            normalized_query="",
        )

    candidates = _build_candidates(funders)
    best = FunderMatch(
        matched_funder=None,
        confidence=0.0,
        alias_match=False,
        matched_alias=None,
        normalized_query=normalized_query,
    )

    for canonical, alias, alias_match, normalized_alias in candidates:
        confidence = _match_confidence(normalized_query, normalized_alias)
        if confidence > best.confidence:
            best = FunderMatch(
                matched_funder=canonical,
                confidence=confidence,
                alias_match=alias_match,
                matched_alias=alias,
                normalized_query=normalized_query,
            )

    if best.confidence < 0.68:
        return FunderMatch(
            matched_funder=None,
            confidence=0.0,
            alias_match=False,
            matched_alias=None,
            normalized_query=normalized_query,
        )

    return best


def _build_candidates(
    funders: Sequence[str] | Mapping[str, Sequence[str]] | None,
) -> tuple[tuple[str, str, bool, str], ...]:
    funder_map: dict[str, Sequence[str]]
    if funders is None:
        funder_map = {funder: DEFAULT_ALIASES.get(funder, ()) for funder in SEED_MCA_FUNDERS}
    elif isinstance(funders, Mapping):
        funder_map = dict(funders)
    else:
        funder_map = {funder: () for funder in funders}

    candidates: list[tuple[str, str, bool, str]] = []
    for canonical, aliases in funder_map.items():
        candidates.append((canonical, canonical, False, normalize_funder_name(canonical)))
        for alias in aliases:
            candidates.append((canonical, alias, True, normalize_funder_name(alias)))

    return tuple(candidates)


def _match_confidence(normalized_query: str, normalized_alias: str) -> float:
    if normalized_query == normalized_alias:
        return 1.0

    if _contains_entity(normalized_query, normalized_alias):
        return 0.90

    ratio = SequenceMatcher(None, normalized_query, normalized_alias).ratio()
    if ratio >= 0.86:
        return round(0.82 + (ratio - 0.86) * 0.10, 4)
    if ratio >= 0.75:
        return round(0.68 + (ratio - 0.75) * 0.45, 4)
    return round(ratio * 0.70, 4)


def _contains_entity(left: str, right: str) -> bool:
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) < 5:
        return False
    return f" {shorter} " in f" {longer} "
