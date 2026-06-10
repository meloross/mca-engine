from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    BuyerCreateRequest,
    BuyerRuleCreateRequest,
    SignalDeliveryRequest,
    SignalReviewRequest,
)
from app.db import get_session
from app.models import (
    AuditLog,
    BuyerAccount,
    BuyerRule,
    Case,
    CaseDocument,
    DeliveryMethod,
    LeadDelivery,
    LeadSignal,
    LeadSignalGrade,
    LeadSignalStatus,
    SignalType,
    UccFiling,
)
from app.services.presentation import (
    analytics_summary,
    serialize_buyer,
    serialize_case,
    serialize_delivery,
    serialize_signal,
    serialize_ucc,
)

router = APIRouter(tags=["signals"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/signals")
def list_signals(
    session: SessionDependency,
    state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    county: str | None = None,
    grade: str | None = None,
    min_score: int | None = None,
    signal_type: str | None = None,
    funder_name: str | None = None,
    business_name: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    has_document_text: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    statement = _filtered_signal_statement(
        state=state,
        county=county,
        grade=grade,
        min_score=min_score,
        signal_type=signal_type,
        funder_name=funder_name,
        business_name=business_name,
        date_from=date_from,
        date_to=date_to,
        status=status,
        has_document_text=has_document_text,
    )
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    offset = (page - 1) * page_size
    statement = statement.order_by(LeadSignal.signal_date.desc(), LeadSignal.score.desc())
    statement = statement.offset(offset).limit(page_size)
    return {
        "items": [serialize_signal(session, signal) for signal in session.scalars(statement).all()],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/signals/{signal_id}")
def get_signal(signal_id: UUID, session: SessionDependency) -> dict[str, object]:
    signal = session.get(LeadSignal, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found.")
    return serialize_signal(session, signal, include_detail=True)


@router.post("/signals/{signal_id}/review")
def review_signal(
    signal_id: UUID,
    body: SignalReviewRequest,
    session: SessionDependency,
) -> dict[str, object]:
    signal = session.get(LeadSignal, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found.")

    signal.status = LeadSignalStatus(body.status)
    if body.status in {"suppressed", "excluded"}:
        signal.exclusion_reason = body.exclusion_reason or body.notes or body.status
    elif body.exclusion_reason:
        signal.exclusion_reason = body.exclusion_reason

    session.add(
        AuditLog(
            actor="admin",
            action=f"signal_{body.status}",
            entity_type="lead_signal",
            entity_id=str(signal.id),
            event_metadata={"notes": body.notes, "exclusion_reason": body.exclusion_reason},
        )
    )
    session.commit()
    session.refresh(signal)
    return serialize_signal(session, signal, include_detail=True)


@router.post("/signals/{signal_id}/deliver")
def deliver_signal(
    signal_id: UUID,
    body: SignalDeliveryRequest,
    session: SessionDependency,
) -> dict[str, object]:
    signal = session.get(LeadSignal, signal_id)
    buyer = session.get(BuyerAccount, body.buyer_account_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found.")
    if buyer is None:
        raise HTTPException(status_code=404, detail="Buyer not found.")
    if not buyer.active:
        raise HTTPException(status_code=400, detail="Buyer account is inactive.")

    delivery = LeadDelivery(
        lead_signal_id=signal.id,
        buyer_account_id=buyer.id,
        delivery_method=DeliveryMethod(body.delivery_method),
    )
    signal.status = LeadSignalStatus.DELIVERED
    session.add(delivery)
    session.add(
        AuditLog(
            actor="admin",
            action="signal_delivered",
            entity_type="lead_signal",
            entity_id=str(signal.id),
            event_metadata={
                "buyer_account_id": str(buyer.id),
                "delivery_method": body.delivery_method,
            },
        )
    )
    session.commit()
    session.refresh(delivery)
    return serialize_delivery(delivery)


@router.get("/cases")
def list_cases(
    session: SessionDependency,
    state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    county: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    statement = select(Case)
    if state:
        statement = statement.where(Case.state == state.upper())
    if county:
        statement = statement.where(Case.county.ilike(f"%{county}%"))
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    cases = session.scalars(
        statement.order_by(Case.filing_date.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [serialize_case(case) for case in cases],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/cases/{case_id}")
def get_case(case_id: UUID, session: SessionDependency) -> dict[str, object]:
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    serialized = serialize_case(case, include_documents=True)
    assert serialized is not None
    return serialized


@router.get("/ucc-filings")
def list_ucc_filings(
    session: SessionDependency,
    state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    statement = select(UccFiling)
    if state:
        statement = statement.where(UccFiling.state == state.upper())
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    filings = session.scalars(
        statement.order_by(UccFiling.filing_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [serialize_ucc(filing) for filing in filings],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/ucc-filings/{ucc_filing_id}")
def get_ucc_filing(ucc_filing_id: UUID, session: SessionDependency) -> dict[str, object]:
    ucc = session.get(UccFiling, ucc_filing_id)
    if ucc is None:
        raise HTTPException(status_code=404, detail="UCC filing not found.")
    serialized = serialize_ucc(ucc)
    assert serialized is not None
    return serialized


@router.get("/buyers")
def list_buyers(session: SessionDependency) -> list[dict[str, object]]:
    return [serialize_buyer(buyer) for buyer in session.scalars(select(BuyerAccount)).all()]


@router.post("/buyers")
def create_buyer(body: BuyerCreateRequest, session: SessionDependency) -> dict[str, object]:
    buyer = BuyerAccount(
        firm_name=body.firm_name,
        contact_name=body.contact_name,
        email=str(body.email),
        phone=body.phone,
        states=[state.upper() for state in body.states],
        counties=body.counties,
        practice_tags=body.practice_tags,
        active=body.active,
    )
    session.add(buyer)
    session.commit()
    session.refresh(buyer)
    return serialize_buyer(buyer)


@router.post("/buyer-rules")
def create_buyer_rule(
    body: BuyerRuleCreateRequest,
    session: SessionDependency,
) -> dict[str, object]:
    buyer = session.get(BuyerAccount, body.buyer_account_id)
    if buyer is None:
        raise HTTPException(status_code=404, detail="Buyer not found.")

    rule = BuyerRule(
        buyer_account_id=buyer.id,
        state=body.state.upper() if body.state else None,
        counties=body.counties,
        min_score=body.min_score,
        signal_types=body.signal_types,
        exclusive=body.exclusive,
        daily_limit=body.daily_limit,
        active=body.active,
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return {
        "id": str(rule.id),
        "buyer_account_id": str(rule.buyer_account_id),
        "state": rule.state,
        "counties": rule.counties,
        "min_score": rule.min_score,
        "signal_types": rule.signal_types,
        "exclusive": rule.exclusive,
        "daily_limit": rule.daily_limit,
        "active": rule.active,
    }


@router.get("/analytics/summary")
def get_analytics_summary(session: SessionDependency) -> dict[str, object]:
    return analytics_summary(session)


def _filtered_signal_statement(
    *,
    state: str | None,
    county: str | None,
    grade: str | None,
    min_score: int | None,
    signal_type: str | None,
    funder_name: str | None,
    business_name: str | None,
    date_from: date | None,
    date_to: date | None,
    status: str | None,
    has_document_text: bool | None,
) -> Select[tuple[LeadSignal]]:
    statement = select(LeadSignal)
    if state:
        statement = statement.where(LeadSignal.state == state.upper())
    if county:
        statement = statement.where(LeadSignal.county.ilike(f"%{county}%"))
    if grade:
        statement = statement.where(LeadSignal.grade == LeadSignalGrade(grade))
    if min_score is not None:
        statement = statement.where(LeadSignal.score >= min_score)
    if signal_type:
        statement = statement.where(LeadSignal.signal_type == SignalType(signal_type))
    if funder_name:
        statement = statement.where(LeadSignal.funder_name.ilike(f"%{funder_name}%"))
    if business_name:
        statement = statement.where(LeadSignal.business_name.ilike(f"%{business_name}%"))
    if date_from:
        statement = statement.where(LeadSignal.signal_date >= date_from)
    if date_to:
        statement = statement.where(LeadSignal.signal_date <= date_to)
    if status:
        statement = statement.where(LeadSignal.status == LeadSignalStatus(status))
    if has_document_text is not None:
        document_case_ids = select(CaseDocument.case_id).where(
            CaseDocument.text_content.is_not(None)
        )
        if has_document_text:
            statement = statement.where(LeadSignal.case_id.in_(document_case_ids))
        else:
            statement = statement.where(
                (LeadSignal.case_id.is_(None)) | (LeadSignal.case_id.not_in(document_case_ids))
            )
    return statement
