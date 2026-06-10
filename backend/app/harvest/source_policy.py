from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AcquisitionMethod,
    AuditLog,
    SourcePolicy,
    SourcePolicySourceType,
    SourcePolicyStatus,
)


@dataclass(frozen=True)
class DefaultSourcePolicy:
    source_code: str
    source_name: str
    state: str | None
    source_type: SourcePolicySourceType
    acquisition_method: AcquisitionMethod
    base_url: str
    terms_url: str | None = None
    robots_url: str | None = None
    automation_allowed: bool | None = None
    live_enabled: bool = False
    requires_login: bool = False
    captcha_observed: bool = False
    requires_payment: bool = False
    rate_limit_seconds: int = 30
    max_pages_per_run: int = 25
    status: SourcePolicyStatus = SourcePolicyStatus.DISABLED
    status_reason: str | None = None


DEFAULT_SOURCE_POLICIES: tuple[DefaultSourcePolicy, ...] = (
    DefaultSourcePolicy(
        source_code="FL_SUNBIZ_DOWNLOADS",
        source_name="Florida Division of Corporations Data Downloads",
        state="FL",
        source_type=SourcePolicySourceType.OFFICIAL_BULK_DOWNLOAD,
        acquisition_method=AcquisitionMethod.OFFICIAL_DOWNLOAD,
        base_url="https://dos.fl.gov/sunbiz/other-services/data-downloads/",
        automation_allowed=True,
        live_enabled=True,
        rate_limit_seconds=2,
        max_pages_per_run=20,
        status=SourcePolicyStatus.ACTIVE,
        status_reason="Official public data-download page; use downloaded bulk files.",
    ),
    DefaultSourcePolicy(
        source_code="FL_UCC_REGISTRY",
        source_name="Florida Secured Transaction Registry",
        state="FL",
        source_type=SourcePolicySourceType.UCC_REGISTRY,
        acquisition_method=AcquisitionMethod.PUBLIC_SEARCH,
        base_url="https://floridaucc.com/",
        terms_url="https://dos.fl.gov/sunbiz/other-services/ucc-information/",
        automation_allowed=None,
        live_enabled=False,
        rate_limit_seconds=30,
        max_pages_per_run=25,
        status=SourcePolicyStatus.NEEDS_PERMISSION,
        status_reason="Enable only after confirming registry terms permit automated public search.",
    ),
    DefaultSourcePolicy(
        source_code="NY_UCC_SEARCH",
        source_name="New York UCC Search",
        state="NY",
        source_type=SourcePolicySourceType.UCC_REGISTRY,
        acquisition_method=AcquisitionMethod.PUBLIC_SEARCH,
        base_url="https://dos.ny.gov/uniform-commercial-code",
        automation_allowed=None,
        live_enabled=False,
        rate_limit_seconds=30,
        max_pages_per_run=25,
        status=SourcePolicyStatus.NEEDS_PERMISSION,
        status_reason="Enable only after confirming NY UCC terms permit automation.",
    ),
    DefaultSourcePolicy(
        source_code="NY_UCC_DATA_DOWNLOAD",
        source_name="New York UCC Authorized Data Download",
        state="NY",
        source_type=SourcePolicySourceType.LICENSED_FEED,
        acquisition_method=AcquisitionMethod.LICENSED_FEED,
        base_url="https://dos.ny.gov/uniform-commercial-code",
        automation_allowed=None,
        live_enabled=False,
        requires_login=True,
        rate_limit_seconds=30,
        max_pages_per_run=5,
        status=SourcePolicyStatus.NEEDS_PERMISSION,
        status_reason="Placeholder for authorized/licensed feed only; configure vendor endpoint.",
    ),
    DefaultSourcePolicy(
        source_code="NY_NYSCEF",
        source_name="NYSCEF Court Records",
        state="NY",
        source_type=SourcePolicySourceType.COURT_PUBLIC_SEARCH,
        acquisition_method=AcquisitionMethod.DISABLED,
        base_url="https://iapps.courts.state.ny.us/nyscef/CaseSearch?TAB=courtDateRange",
        automation_allowed=False,
        live_enabled=False,
        requires_login=False,
        captcha_observed=False,
        status=SourcePolicyStatus.BLOCKED_BY_TERMS,
        status_reason=(
            "Do not automate NYSCEF in this product; use manual import "
            "or authorized access."
        ),
    ),
    DefaultSourcePolicy(
        source_code="FL_EFILING_PORTAL",
        source_name="Florida Courts E-Filing Portal",
        state="FL",
        source_type=SourcePolicySourceType.COURT_LOGIN_PORTAL,
        acquisition_method=AcquisitionMethod.DISABLED,
        base_url="https://myflcourtaccess.com/authority/",
        automation_allowed=False,
        live_enabled=False,
        requires_login=True,
        captcha_observed=False,
        status=SourcePolicyStatus.BLOCKED_BY_TERMS,
        status_reason="Do not bypass registration, login, CAPTCHA, or access controls.",
    ),
)

BLOCKED_SOURCE_CODES = {"NY_NYSCEF", "FL_EFILING_PORTAL"}
CONFIRMABLE_SOURCE_CODES = {"FL_UCC_REGISTRY", "NY_UCC_SEARCH", "NY_UCC_DATA_DOWNLOAD"}


class SourcePolicyError(ValueError):
    """Raised when a source policy transition would violate compliance rules."""


def ensure_default_source_policies(session: Session) -> list[SourcePolicy]:
    existing = {
        policy.source_code: policy
        for policy in session.scalars(select(SourcePolicy)).all()
    }
    policies: list[SourcePolicy] = []
    for default in DEFAULT_SOURCE_POLICIES:
        policy = existing.get(default.source_code)
        if policy is None:
            policy = SourcePolicy(**_default_to_model_kwargs(default))
            session.add(policy)
            policies.append(policy)
            continue
        _refresh_static_fields(policy, default)
        policies.append(policy)
    session.flush()
    return policies


def list_source_policies(
    session: Session,
    *,
    state: str | None = None,
) -> list[SourcePolicy]:
    ensure_default_source_policies(session)
    statement = select(SourcePolicy).order_by(SourcePolicy.state, SourcePolicy.source_code)
    if state:
        statement = statement.where(SourcePolicy.state == state.upper())
    return list(session.scalars(statement).all())


def get_source_policy(session: Session, source_code: str) -> SourcePolicy:
    ensure_default_source_policies(session)
    policy = session.scalar(
        select(SourcePolicy).where(SourcePolicy.source_code == source_code.upper())
    )
    if policy is None:
        raise SourcePolicyError(f"Unknown source policy: {source_code}")
    return policy


def enable_source_policy(
    session: Session,
    source_code: str,
    *,
    actor: str = "admin",
    confirm_terms_reviewed: bool = False,
) -> SourcePolicy:
    policy = get_source_policy(session, source_code)
    if policy.source_code in BLOCKED_SOURCE_CODES or policy.automation_allowed is False:
        raise SourcePolicyError("This source is blocked by policy and cannot be enabled.")

    if policy.source_code in CONFIRMABLE_SOURCE_CODES and not confirm_terms_reviewed:
        raise SourcePolicyError(
            "Confirm source terms review before enabling this live acquisition source."
        )

    policy.automation_allowed = True
    policy.live_enabled = True
    policy.status = SourcePolicyStatus.ACTIVE
    policy.status_reason = "Enabled after admin-confirmed source terms review."
    policy.last_checked_at = datetime.now(UTC)
    _audit_policy(session, actor, "source_policy_enabled", policy)
    session.flush()
    return policy


def disable_source_policy(
    session: Session,
    source_code: str,
    *,
    actor: str = "admin",
) -> SourcePolicy:
    policy = get_source_policy(session, source_code)
    policy.live_enabled = False
    if policy.source_code in BLOCKED_SOURCE_CODES:
        policy.status = SourcePolicyStatus.BLOCKED_BY_TERMS
    elif policy.source_code in CONFIRMABLE_SOURCE_CODES and policy.automation_allowed is not True:
        policy.status = SourcePolicyStatus.NEEDS_PERMISSION
    else:
        policy.status = SourcePolicyStatus.DISABLED
    policy.status_reason = policy.status_reason or "Disabled by admin."
    policy.last_checked_at = datetime.now(UTC)
    _audit_policy(session, actor, "source_policy_disabled", policy)
    session.flush()
    return policy


def check_source_policy(
    session: Session,
    source_code: str,
    *,
    actor: str = "admin",
) -> SourcePolicy:
    policy = get_source_policy(session, source_code)
    if policy.source_code in BLOCKED_SOURCE_CODES:
        policy.live_enabled = False
        policy.automation_allowed = False
        policy.status = SourcePolicyStatus.BLOCKED_BY_TERMS
    elif policy.source_code in CONFIRMABLE_SOURCE_CODES:
        if policy.live_enabled and policy.automation_allowed is True:
            policy.status = SourcePolicyStatus.ACTIVE
        else:
            policy.live_enabled = False
            policy.status = SourcePolicyStatus.NEEDS_PERMISSION
    elif policy.automation_allowed is True and policy.live_enabled:
        policy.status = SourcePolicyStatus.ACTIVE
    elif policy.live_enabled:
        policy.status = SourcePolicyStatus.ERROR
        policy.status_reason = "Live source is enabled without explicit automation permission."
    else:
        policy.status = SourcePolicyStatus.DISABLED
    policy.last_checked_at = datetime.now(UTC)
    _audit_policy(session, actor, "source_policy_checked", policy)
    session.flush()
    return policy


def live_enabled_policies(
    session: Session,
    *,
    states: Iterable[str] | None = None,
) -> list[SourcePolicy]:
    normalized_states = {state.upper() for state in states or ()}
    policies = list_source_policies(session)
    filtered: list[SourcePolicy] = []
    for policy in policies:
        if normalized_states and policy.state not in normalized_states:
            continue
        if policy.live_enabled and policy.status == SourcePolicyStatus.ACTIVE:
            filtered.append(policy)
    return filtered


def serialize_source_policy(policy: SourcePolicy) -> dict[str, object]:
    return {
        "id": str(policy.id),
        "source_code": policy.source_code,
        "source_name": policy.source_name,
        "state": policy.state,
        "source_type": policy.source_type.value,
        "acquisition_method": policy.acquisition_method.value,
        "base_url": policy.base_url,
        "terms_url": policy.terms_url,
        "robots_url": policy.robots_url,
        "automation_allowed": policy.automation_allowed,
        "live_enabled": policy.live_enabled,
        "requires_login": policy.requires_login,
        "captcha_observed": policy.captcha_observed,
        "requires_payment": policy.requires_payment,
        "rate_limit_seconds": policy.rate_limit_seconds,
        "max_pages_per_run": policy.max_pages_per_run,
        "status": policy.status.value,
        "status_reason": policy.status_reason,
        "last_checked_at": policy.last_checked_at.isoformat() if policy.last_checked_at else None,
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }


def _default_to_model_kwargs(default: DefaultSourcePolicy) -> dict[str, object]:
    return {
        "source_code": default.source_code,
        "source_name": default.source_name,
        "state": default.state,
        "source_type": default.source_type,
        "acquisition_method": default.acquisition_method,
        "base_url": default.base_url,
        "terms_url": default.terms_url,
        "robots_url": default.robots_url,
        "automation_allowed": default.automation_allowed,
        "live_enabled": default.live_enabled,
        "requires_login": default.requires_login,
        "captcha_observed": default.captcha_observed,
        "requires_payment": default.requires_payment,
        "rate_limit_seconds": default.rate_limit_seconds,
        "max_pages_per_run": default.max_pages_per_run,
        "status": default.status,
        "status_reason": default.status_reason,
    }


def _refresh_static_fields(policy: SourcePolicy, default: DefaultSourcePolicy) -> None:
    policy.source_name = default.source_name
    policy.state = default.state
    policy.source_type = default.source_type
    policy.acquisition_method = default.acquisition_method
    policy.base_url = default.base_url
    policy.terms_url = default.terms_url
    policy.robots_url = default.robots_url
    policy.requires_login = default.requires_login
    policy.captcha_observed = default.captcha_observed
    policy.requires_payment = default.requires_payment
    if policy.source_code in BLOCKED_SOURCE_CODES:
        policy.automation_allowed = False
        policy.live_enabled = False
        policy.status = SourcePolicyStatus.BLOCKED_BY_TERMS
        policy.status_reason = default.status_reason
    if policy.status_reason is None:
        policy.status_reason = default.status_reason


def _audit_policy(
    session: Session,
    actor: str,
    action: str,
    policy: SourcePolicy,
) -> None:
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            entity_type="source_policy",
            entity_id=policy.source_code,
            event_metadata=serialize_source_policy(policy),
        )
    )
