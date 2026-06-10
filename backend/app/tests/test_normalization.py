from __future__ import annotations

import re

import pytest

from app.compliance import hash_sensitive_value, normalize_business_name, normalize_funder_name


def test_normalize_business_name_removes_noise_and_legal_suffix() -> None:
    assert normalize_business_name("The Açaí & Bagel Shop, LLC") == "ACAI AND BAGEL SHOP"


def test_normalize_funder_name_matches_alias_shape() -> None:
    assert normalize_funder_name("ABC Funding, Inc.") == "ABC FUNDING"


def test_hash_sensitive_value_is_deterministic_and_non_reversible_shape() -> None:
    first = hash_sensitive_value("Person@example.com ", pepper="unit-test-pepper")
    second = hash_sensitive_value(" person@example.com", pepper="unit-test-pepper")

    assert first == second
    assert first != "person@example.com"
    assert re.fullmatch(r"[0-9a-f]{64}", first)


def test_hash_sensitive_value_rejects_empty_values() -> None:
    with pytest.raises(ValueError):
        hash_sensitive_value("   ", pepper="unit-test-pepper")
