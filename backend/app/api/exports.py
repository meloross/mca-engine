from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.exports import ExportFilters, export_form_leads_bytes, export_signals_bytes
from app.exports.schemas import ExportFormat, ExportResult

router = APIRouter(tags=["exports"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/exports/signals.csv")
def export_signals_csv(
    session: SessionDependency,
    filters: Annotated[ExportFilters, Depends(_export_filters)],
) -> Response:
    return _download_response(export_signals_bytes(session, filters=filters, export_format="csv"))


@router.get("/exports/signals.xlsx")
def export_signals_xlsx(
    session: SessionDependency,
    filters: Annotated[ExportFilters, Depends(_export_filters)],
) -> Response:
    return _download_response(export_signals_bytes(session, filters=filters, export_format="xlsx"))


@router.get("/exports/form-leads.csv")
def export_form_leads_csv(
    session: SessionDependency,
    filters: Annotated[ExportFilters, Depends(_export_filters)],
) -> Response:
    return _download_response(
        export_form_leads_bytes(session, filters=filters, export_format="csv")
    )


@router.get("/exports/form-leads.xlsx")
def export_form_leads_xlsx(
    session: SessionDependency,
    filters: Annotated[ExportFilters, Depends(_export_filters)],
) -> Response:
    return _download_response(
        export_form_leads_bytes(session, filters=filters, export_format="xlsx")
    )


def _export_filters(
    state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    county: str | None = None,
    grade: str | None = None,
    min_score: int | None = None,
    signal_type: str | None = None,
    funder_name: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    only_high_value: bool = False,
    include_suppressed: bool = False,
    include_excluded: bool = False,
) -> ExportFilters:
    return ExportFilters.from_state(
        state=state,
        county=county,
        grade=grade,
        min_score=min_score,
        signal_type=signal_type,
        funder_name=funder_name,
        date_from=date_from,
        date_to=date_to,
        status=status,
        only_high_value=only_high_value,
        include_suppressed=include_suppressed,
        include_excluded=include_excluded,
    )


def _download_response(result: ExportResult) -> Response:
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "X-Export-Row-Count": str(result.row_count),
        },
    )


def export_media_type(export_format: ExportFormat) -> str:
    return "text/csv" if export_format == "csv" else (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
