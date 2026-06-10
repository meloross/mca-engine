from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import McaDefenseLeadFormRequest
from app.db import get_session
from app.models import FormLead
from app.services.form_leads import (
    create_form_lead,
    route_form_lead,
    serialize_form_lead,
)

router = APIRouter(tags=["form-leads"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/lead-form/mca-defense")
def submit_mca_defense_form(
    body: McaDefenseLeadFormRequest,
    request: Request,
    session: SessionDependency,
) -> dict[str, object]:
    client_host = request.client.host if request.client else "unknown"
    form_lead = create_form_lead(
        session,
        payload=body,
        ip_address=client_host,
        user_agent=request.headers.get("user-agent"),
    )
    return serialize_form_lead(form_lead, include_detail=True)


@router.get("/admin/form-leads")
def list_form_leads(
    session: SessionDependency,
    state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    status: str | None = None,
    min_score: int | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    statement = select(FormLead)
    if state:
        statement = statement.where(FormLead.state == state.upper())
    if status:
        statement = statement.where(FormLead.status == status)
    if min_score is not None:
        statement = statement.where(FormLead.score >= min_score)

    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    form_leads = session.scalars(
        statement.order_by(FormLead.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [serialize_form_lead(form_lead) for form_lead in form_leads],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/admin/form-leads/{form_lead_id}")
def get_form_lead(form_lead_id: UUID, session: SessionDependency) -> dict[str, object]:
    form_lead = session.get(FormLead, form_lead_id)
    if form_lead is None:
        raise HTTPException(status_code=404, detail="Form lead not found.")
    return serialize_form_lead(form_lead, include_detail=True)


@router.post("/admin/form-leads/{form_lead_id}/route")
def route_form_lead_to_buyers(
    form_lead_id: UUID,
    session: SessionDependency,
) -> dict[str, object]:
    form_lead = session.get(FormLead, form_lead_id)
    if form_lead is None:
        raise HTTPException(status_code=404, detail="Form lead not found.")
    try:
        return route_form_lead(session, form_lead)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
