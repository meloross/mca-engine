from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    BuyerAccount,
    Case,
    CaseDocument,
    LeadDelivery,
    LeadSignal,
    Source,
    UccFiling,
)
from app.scoring import score_signal

SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b\d{9}\b"),
    re.compile(r"\b\d{8,17}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),
)


def redact_sensitive(value: object) -> object:
    if not isinstance(value, str):
        return value

    redacted = value
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def serialize_signal(
    session: Session,
    signal: LeadSignal,
    *,
    include_detail: bool = False,
) -> dict[str, Any]:
    source = session.get(Source, signal.source_id)
    case = session.get(Case, signal.case_id) if signal.case_id else None
    ucc = session.get(UccFiling, signal.ucc_filing_id) if signal.ucc_filing_id else None
    explanation = explain_signal(session, signal)
    payload: dict[str, Any] = {
        "id": str(signal.id),
        "signal_type": signal.signal_type.value,
        "state": signal.state,
        "county": signal.county,
        "business_name": redact_sensitive(signal.business_name),
        "normalized_business_name": signal.normalized_business_name,
        "funder_name": redact_sensitive(signal.funder_name),
        "case_id": str(signal.case_id) if signal.case_id else None,
        "ucc_filing_id": str(signal.ucc_filing_id) if signal.ucc_filing_id else None,
        "signal_date": signal.signal_date.isoformat(),
        "title": redact_sensitive(signal.title),
        "summary": redact_sensitive(signal.summary),
        "score": signal.score,
        "risk_score": signal.risk_score,
        "grade": signal.grade.value,
        "status": signal.status.value,
        "exclusion_reason": redact_sensitive(signal.exclusion_reason),
        "compliance_flags": signal.compliance_flags,
        "source_id": str(signal.source_id),
        "source_name": source.name if source else None,
        "source_url": signal.source_url,
        "created_at": signal.created_at.isoformat() if signal.created_at else None,
        "updated_at": signal.updated_at.isoformat() if signal.updated_at else None,
        "keyword_hits": explanation["keyword_hits"],
        "keyword_groups": explanation["keyword_groups"],
        "score_reasons": explanation["score_reasons"],
    }
    if include_detail:
        payload["case"] = serialize_case(case, include_documents=True) if case else None
        payload["ucc_filing"] = serialize_ucc(ucc) if ucc else None
        payload["deliveries"] = [
            serialize_delivery(delivery)
            for delivery in session.scalars(
                select(LeadDelivery).where(LeadDelivery.lead_signal_id == signal.id)
            )
        ]
        payload["audit_log"] = [
            serialize_audit_log(event)
            for event in session.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == "lead_signal", AuditLog.entity_id == str(signal.id))
                .order_by(AuditLog.created_at.desc())
            )
        ]
    return payload


def serialize_case(case: Case | None, *, include_documents: bool = False) -> dict[str, Any] | None:
    if case is None:
        return None

    payload: dict[str, Any] = {
        "id": str(case.id),
        "state": case.state,
        "county": case.county,
        "court_name": case.court_name,
        "case_number": redact_sensitive(case.case_number),
        "case_type": case.case_type,
        "filing_date": case.filing_date.isoformat() if case.filing_date else None,
        "last_activity_date": (
            case.last_activity_date.isoformat() if case.last_activity_date else None
        ),
        "caption": redact_sensitive(case.caption),
        "plaintiff_names": [redact_sensitive(name) for name in case.plaintiff_names],
        "defendant_names": [redact_sensitive(name) for name in case.defendant_names],
        "attorney_names": [redact_sensitive(name) for name in case.attorney_names],
        "source_id": str(case.source_id),
        "source_url": case.source_url,
        "normalized_key": case.normalized_key,
    }
    if include_documents:
        payload["documents"] = [serialize_case_document(document) for document in case.documents]
    return payload


def serialize_case_document(document: CaseDocument) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "case_id": str(document.case_id),
        "document_type": document.document_type,
        "document_title": redact_sensitive(document.document_title),
        "filed_at": document.filed_at.isoformat() if document.filed_at else None,
        "source_url": document.source_url,
        "text_content": redact_sensitive(document.text_content),
        "has_mca_keywords": document.has_mca_keywords,
        "keyword_hits": document.keyword_hits,
    }


def serialize_ucc(ucc: UccFiling | None) -> dict[str, Any] | None:
    if ucc is None:
        return None

    return {
        "id": str(ucc.id),
        "state": ucc.state,
        "filing_number": redact_sensitive(ucc.filing_number),
        "filing_type": ucc.filing_type,
        "filing_date": ucc.filing_date.isoformat() if ucc.filing_date else None,
        "lapse_date": ucc.lapse_date.isoformat() if ucc.lapse_date else None,
        "debtor_name": redact_sensitive(ucc.debtor_name),
        "debtor_address": redact_sensitive(ucc.debtor_address),
        "secured_party_name": redact_sensitive(ucc.secured_party_name),
        "secured_party_address": redact_sensitive(ucc.secured_party_address),
        "collateral_text": redact_sensitive(ucc.collateral_text),
        "source_id": str(ucc.source_id),
        "source_url": ucc.source_url,
        "normalized_key": ucc.normalized_key,
    }


def serialize_buyer(buyer: BuyerAccount) -> dict[str, Any]:
    return {
        "id": str(buyer.id),
        "firm_name": redact_sensitive(buyer.firm_name),
        "contact_name": redact_sensitive(buyer.contact_name),
        "email": _redact_email(buyer.email),
        "phone": _redact_phone(buyer.phone),
        "states": buyer.states,
        "counties": buyer.counties,
        "practice_tags": buyer.practice_tags,
        "active": buyer.active,
        "created_at": buyer.created_at.isoformat() if buyer.created_at else None,
    }


def serialize_delivery(delivery: LeadDelivery) -> dict[str, Any]:
    return {
        "id": str(delivery.id),
        "lead_signal_id": str(delivery.lead_signal_id),
        "buyer_account_id": str(delivery.buyer_account_id),
        "delivery_method": delivery.delivery_method.value,
        "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
        "accepted": delivery.accepted,
        "rejected_reason": redact_sensitive(delivery.rejected_reason),
    }


def serialize_audit_log(event: AuditLog) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "actor": event.actor,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "metadata": _redact_mapping(event.event_metadata),
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def explain_signal(session: Session, signal: LeadSignal) -> dict[str, Any]:
    record = _score_record_from_signal(session, signal)
    score_result = score_signal(record, as_of=signal.signal_date)
    return {
        "keyword_hits": list(score_result.keyword_classification.keyword_hits),
        "keyword_groups": {
            key: list(value) for key, value in score_result.keyword_classification.groups.items()
        },
        "score_reasons": list(score_result.reasons),
        "computed_score": score_result.score,
        "stored_score": signal.score,
    }


def analytics_summary(session: Session) -> dict[str, Any]:
    signals = list(session.scalars(select(LeadSignal)).all())
    sources = {source.id: source.name for source in session.scalars(select(Source)).all()}
    excluded = [
        signal.exclusion_reason or "status:excluded"
        for signal in signals
        if signal.status.value == "excluded" or signal.exclusion_reason
    ]

    return {
        "total_signals": len(signals),
        "signals_by_state": dict(Counter(signal.state for signal in signals)),
        "signals_by_grade": dict(Counter(signal.grade.value for signal in signals)),
        "signals_by_source": dict(
            Counter(sources.get(signal.source_id, "unknown") for signal in signals)
        ),
        "average_score": (
            round(sum(signal.score for signal in signals) / len(signals), 2) if signals else 0
        ),
        "newest_filing_timestamp": (
            max(signal.signal_date for signal in signals).isoformat() if signals else None
        ),
        "top_funders": _top_counter(signal.funder_name for signal in signals if signal.funder_name),
        "top_counties": _top_counter(signal.county for signal in signals if signal.county),
        "exclusion_counts": dict(Counter(excluded)),
    }


def _score_record_from_signal(session: Session, signal: LeadSignal) -> dict[str, Any]:
    case = session.get(Case, signal.case_id) if signal.case_id else None
    ucc = session.get(UccFiling, signal.ucc_filing_id) if signal.ucc_filing_id else None
    if case:
        documents = list(
            session.scalars(select(CaseDocument).where(CaseDocument.case_id == case.id)).all()
        )
        return {
            "signal_type": signal.signal_type.value,
            "caption": case.caption,
            "plaintiff_names": case.plaintiff_names,
            "defendant_names": case.defendant_names,
            "document_text": "\n".join(document.text_content or "" for document in documents),
            "filing_date": case.filing_date or signal.signal_date,
            "defense_attorney_names": [],
            "source_automation_allowed": True,
        }
    if ucc:
        return {
            "signal_type": signal.signal_type.value,
            "ucc_secured_party": ucc.secured_party_name,
            "secured_party_name": ucc.secured_party_name,
            "debtor_name": ucc.debtor_name,
            "defendant_names": [ucc.debtor_name] if ucc.debtor_name else [],
            "ucc_collateral_text": ucc.collateral_text,
            "filing_date": ucc.filing_date or signal.signal_date,
            "source_automation_allowed": True,
        }
    return {
        "signal_type": signal.signal_type.value,
        "funder_name": signal.funder_name,
        "defendant_names": [signal.business_name],
        "document_text": signal.summary,
        "filing_date": signal.signal_date,
        "source_automation_allowed": True,
    }


def document_datetime_from_date(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=UTC)


def _redact_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return value
    local, domain = value.split("@", 1)
    return f"{local[:2]}***@{domain}"


def _redact_phone(value: str | None) -> str | None:
    if not value:
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "***"
    return f"***-***-{digits[-4:]}"


def _redact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    return {key: redact_sensitive(item) for key, item in value.items()}


def _top_counter(values: Any) -> list[dict[str, Any]]:
    counts = Counter(values)
    return [{"value": value, "count": count} for value, count in counts.most_common(10)]
