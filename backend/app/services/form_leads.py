from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.compliance import hash_sensitive_value, normalize_business_name
from app.models import (
    AuditLog,
    BuyerAccount,
    BuyerRule,
    ConsentEvent,
    FormLead,
    LeadSignalGrade,
)
from app.scoring.form_lead_score import score_form_lead
from app.services.presentation import redact_sensitive, serialize_buyer

FORM_LEAD_SIGNAL_TYPE = "mca_defense_form"
DEFAULT_LEAD_FORM_DISCLAIMER = (
    "Submitting this form does not create an attorney-client relationship and is not legal "
    "advice. A participating attorney may contact you only if you provide express consent."
)


def create_form_lead(
    session: Session,
    *,
    payload: Any,
    ip_address: str,
    user_agent: str | None,
) -> FormLead:
    score = score_form_lead(payload)
    form_lead = FormLead(
        state=payload.state.upper(),
        business_name=payload.business_name,
        contact_name=payload.contact_name,
        email=payload.email,
        phone=payload.phone,
        preferred_contact_method=payload.preferred_contact_method,
        legal_issue_type=payload.legal_issue_type,
        has_been_sued=payload.has_been_sued,
        case_state=payload.case_state.upper() if payload.case_state else None,
        case_county=payload.case_county,
        case_number=payload.case_number,
        mca_funder_names=payload.mca_funder_names,
        daily_weekly_payment_amount=payload.daily_weekly_payment_amount,
        total_mca_balance_range=payload.total_mca_balance_range,
        bank_account_frozen=payload.bank_account_frozen,
        ucc_lien_issue=payload.ucc_lien_issue,
        court_deadline_date=payload.court_deadline_date,
        has_attorney=payload.has_attorney,
        consent_to_contact=payload.consent_to_contact,
        consent_text=payload.consent_text,
        disclaimer_text=payload.disclaimer_text,
        page_url=payload.page_url,
        ip_hash=hash_sensitive_value(ip_address),
        user_agent=user_agent,
        source_campaign=payload.source_campaign,
        score=score.score,
        grade=LeadSignalGrade(score.grade),
        status="excluded" if score.excluded else "new",
    )
    session.add(form_lead)
    session.flush()

    if payload.consent_to_contact:
        session.add(
            ConsentEvent(
                form_lead_id=str(form_lead.id),
                consent_text=payload.consent_text,
                page_url=payload.page_url,
                ip_address_hash=form_lead.ip_hash,
                user_agent=user_agent,
                consented_at=datetime.now(UTC),
                buyer_disclosure=payload.disclaimer_text,
            )
        )

    session.add(
        AuditLog(
            actor="public_form",
            action="form_lead_created",
            entity_type="form_lead",
            entity_id=str(form_lead.id),
            event_metadata={
                "score": score.score,
                "grade": score.grade,
                "excluded": score.excluded,
                "exclusion_reasons": list(score.exclusion_reasons),
                "source_campaign": payload.source_campaign,
            },
        )
    )
    session.commit()
    session.refresh(form_lead)
    return form_lead


def route_form_lead(session: Session, form_lead: FormLead) -> dict[str, Any]:
    if not form_lead.consent_to_contact:
        raise ValueError("Cannot route a form lead without express contact consent.")
    if form_lead.grade == LeadSignalGrade.EXCLUDE or form_lead.status == "excluded":
        raise ValueError("Cannot route an excluded form lead.")

    rules = session.scalars(
        select(BuyerRule).join(BuyerAccount).where(
            BuyerRule.active.is_(True),
            BuyerAccount.active.is_(True),
        )
    ).all()
    matching_rules = [rule for rule in rules if buyer_rule_matches_form_lead(rule, form_lead)]
    if not matching_rules:
        raise LookupError("No active buyer rule matches this form lead.")

    matching_rules.sort(key=lambda rule: (rule.exclusive, rule.min_score), reverse=True)
    selected_rules = [matching_rules[0]] if matching_rules[0].exclusive else matching_rules
    buyers = [rule.buyer_account for rule in selected_rules]

    form_lead.status = "routed"
    session.add(
        AuditLog(
            actor="admin",
            action="form_lead_routed",
            entity_type="form_lead",
            entity_id=str(form_lead.id),
            event_metadata={
                "buyer_account_ids": [str(buyer.id) for buyer in buyers],
                "routing_signal_type": FORM_LEAD_SIGNAL_TYPE,
            },
        )
    )
    session.commit()
    session.refresh(form_lead)
    return {
        "form_lead": serialize_form_lead(form_lead),
        "routed_buyers": [serialize_buyer(buyer) for buyer in buyers],
    }


def buyer_rule_matches_form_lead(rule: BuyerRule, form_lead: FormLead) -> bool:
    buyer = rule.buyer_account
    lead_state = form_lead.state.upper()
    lead_county = (form_lead.case_county or "").lower()

    if not form_lead.consent_to_contact:
        return False
    if form_lead.grade == LeadSignalGrade.EXCLUDE or form_lead.status == "excluded":
        return False
    if rule.state and rule.state.upper() != lead_state:
        return False
    if buyer.states and lead_state not in {state.upper() for state in buyer.states}:
        return False
    if rule.counties and lead_county not in {county.lower() for county in rule.counties}:
        return False
    if form_lead.score < rule.min_score:
        return False
    return not rule.signal_types or FORM_LEAD_SIGNAL_TYPE in {
        signal_type.lower() for signal_type in rule.signal_types
    }


def serialize_form_lead(form_lead: FormLead, *, include_detail: bool = False) -> dict[str, Any]:
    score = score_form_lead(form_lead)
    payload: dict[str, Any] = {
        "id": str(form_lead.id),
        "state": form_lead.state,
        "business_name": redact_sensitive(form_lead.business_name),
        "normalized_business_name": _safe_normalized_business_name(form_lead.business_name),
        "contact_name": redact_sensitive(form_lead.contact_name),
        "email": form_lead.email,
        "phone": form_lead.phone,
        "preferred_contact_method": form_lead.preferred_contact_method,
        "legal_issue_type": form_lead.legal_issue_type,
        "has_been_sued": form_lead.has_been_sued,
        "case_state": form_lead.case_state,
        "case_county": form_lead.case_county,
        "case_number": redact_sensitive(form_lead.case_number),
        "mca_funder_names": [redact_sensitive(value) for value in form_lead.mca_funder_names],
        "daily_weekly_payment_amount": _decimal_to_string(form_lead.daily_weekly_payment_amount),
        "total_mca_balance_range": form_lead.total_mca_balance_range,
        "bank_account_frozen": form_lead.bank_account_frozen,
        "ucc_lien_issue": form_lead.ucc_lien_issue,
        "court_deadline_date": form_lead.court_deadline_date.isoformat()
        if form_lead.court_deadline_date
        else None,
        "has_attorney": form_lead.has_attorney,
        "consent_to_contact": form_lead.consent_to_contact,
        "consent_text": form_lead.consent_text,
        "disclaimer_text": form_lead.disclaimer_text,
        "page_url": form_lead.page_url,
        "ip_hash": form_lead.ip_hash,
        "user_agent": form_lead.user_agent,
        "source_campaign": form_lead.source_campaign,
        "score": form_lead.score,
        "grade": form_lead.grade.value,
        "status": form_lead.status,
        "score_reasons": list(score.reasons),
        "exclusion_reasons": list(score.exclusion_reasons),
        "created_at": form_lead.created_at.isoformat() if form_lead.created_at else None,
    }
    if not include_detail:
        for key in ("consent_text", "disclaimer_text", "user_agent"):
            payload.pop(key, None)
    return payload


def _decimal_to_string(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _safe_normalized_business_name(value: str) -> str:
    try:
        return normalize_business_name(value)
    except ValueError:
        return ""


def _buyers_from_rules(rules: Sequence[BuyerRule]) -> list[BuyerAccount]:
    return [rule.buyer_account for rule in rules]
