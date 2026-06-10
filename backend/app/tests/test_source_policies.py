from __future__ import annotations

from app.harvest.source_policy import (
    BLOCKED_SOURCE_CODES,
    CONFIRMABLE_SOURCE_CODES,
    DEFAULT_SOURCE_POLICIES,
    serialize_source_policy,
)
from app.models import AcquisitionMethod, SourcePolicy, SourcePolicyStatus


def test_default_source_policies_capture_compliance_posture() -> None:
    policies = {policy.source_code: policy for policy in DEFAULT_SOURCE_POLICIES}

    assert policies["FL_SUNBIZ_DOWNLOADS"].status == SourcePolicyStatus.ACTIVE
    assert policies["FL_SUNBIZ_DOWNLOADS"].automation_allowed is True
    assert policies["FL_SUNBIZ_DOWNLOADS"].live_enabled is True
    assert policies["NY_NYSCEF"].status == SourcePolicyStatus.BLOCKED_BY_TERMS
    assert policies["NY_NYSCEF"].automation_allowed is False
    assert policies["FL_EFILING_PORTAL"].requires_login is True
    assert policies["FL_EFILING_PORTAL"].live_enabled is False
    assert "FL_UCC_REGISTRY" in CONFIRMABLE_SOURCE_CODES
    assert "NY_UCC_SEARCH" in CONFIRMABLE_SOURCE_CODES
    assert {"NY_NYSCEF", "FL_EFILING_PORTAL"} == BLOCKED_SOURCE_CODES


def test_source_policy_serializer_uses_public_fields() -> None:
    policy = SourcePolicy(
        source_code="TEST_SOURCE",
        source_name="Test Source",
        state="FL",
        source_type=next(policy.source_type for policy in DEFAULT_SOURCE_POLICIES),
        acquisition_method=AcquisitionMethod.OFFICIAL_DOWNLOAD,
        base_url="https://example.test",
        automation_allowed=True,
        live_enabled=True,
        requires_login=False,
        captcha_observed=False,
        requires_payment=False,
        rate_limit_seconds=5,
        max_pages_per_run=2,
        status=SourcePolicyStatus.ACTIVE,
        status_reason="Test only.",
    )

    payload = serialize_source_policy(policy)

    assert payload["source_code"] == "TEST_SOURCE"
    assert payload["automation_allowed"] is True
    assert payload["status"] == "active"
