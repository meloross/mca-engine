from __future__ import annotations

import re

from app.compliance import normalize_business_name


def normalize_contact_value(value: str) -> str:
    normalized_phone = normalize_us_phone(value)
    if normalized_phone:
        return normalized_phone
    return value.strip().lower()


def normalize_us_phone(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"+1{digits}"


def same_business(query_name: str, candidate_name: str) -> bool:
    try:
        return normalize_business_name(query_name) == normalize_business_name(candidate_name)
    except ValueError:
        return False


def domain_from_url(value: str) -> str:
    cleaned = value.lower().split("//", 1)[-1]
    return cleaned.split("/", 1)[0].removeprefix("www.")
