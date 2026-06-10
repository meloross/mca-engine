from __future__ import annotations

import hashlib
import os
import re
import unicodedata

LEGAL_SUFFIXES = {
    "CO",
    "COMPANY",
    "CORP",
    "CORPORATION",
    "INC",
    "INCORPORATED",
    "LLC",
    "L.L.C",
    "LP",
    "L.P",
    "LTD",
    "LIMITED",
    "PLLC",
    "P.L.L.C",
}

PUNCTUATION_RE = re.compile(r"[^A-Z0-9& ]+")
SPACE_RE = re.compile(r"\s+")


def _ascii_upper(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.upper()


def _normalize_entity_name(value: str, *, drop_legal_suffixes: bool) -> str:
    if value is None:
        raise ValueError("Cannot normalize a null value.")

    cleaned = _ascii_upper(value)
    cleaned = cleaned.replace("&", " AND ")
    cleaned = PUNCTUATION_RE.sub(" ", cleaned)
    words = SPACE_RE.sub(" ", cleaned).strip().split(" ")

    if words[:1] == ["THE"]:
        words = words[1:]

    if drop_legal_suffixes:
        while words and words[-1] in LEGAL_SUFFIXES:
            words.pop()

    return " ".join(words)


def normalize_business_name(value: str) -> str:
    """Normalize public business names for dedupe and matching."""

    return _normalize_entity_name(value, drop_legal_suffixes=True)


def normalize_funder_name(value: str) -> str:
    """Normalize MCA funder names and aliases using the same entity rules."""

    return _normalize_entity_name(value, drop_legal_suffixes=True)


def hash_sensitive_value(value: str, *, pepper: str | None = None) -> str:
    """Hash suppressions and consent metadata without storing raw sensitive values."""

    if value is None:
        raise ValueError("Cannot hash a null value.")

    normalized = SPACE_RE.sub(" ", value.strip().lower())
    if not normalized:
        raise ValueError("Cannot hash an empty value.")

    secret = (
        pepper if pepper is not None else os.getenv("SENSITIVE_HASH_PEPPER", "dev-only-change-me")
    )
    payload = f"{secret}:{normalized}".encode()
    return hashlib.sha256(payload).hexdigest()
