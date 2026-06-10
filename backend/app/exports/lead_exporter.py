from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.classifiers import classify_text
from app.exports.formatters import rows_to_csv, rows_to_xlsx
from app.exports.permissions import NO_CONSENT_REDACTED, consented_form_value, public_export_value
from app.exports.schemas import ExportFilters, ExportFormat, ExportResult, ExportType
from app.models import (
    Case,
    CaseDocument,
    ConsentEvent,
    FormLead,
    LeadSignal,
    LeadSignalGrade,
    LeadSignalStatus,
    RawArtifact,
    SignalType,
    Source,
    UccFiling,
)

CSV_MEDIA_TYPE = "text/csv"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

PUBLIC_SIGNAL_COLUMNS = [
    "signal_id",
    "grade",
    "score",
    "risk_score",
    "status",
    "signal_type",
    "signal_date",
    "state",
    "county",
    "business_name",
    "normalized_business_name",
    "funder_name",
    "title",
    "summary",
    "case_number",
    "court_name",
    "case_type",
    "filing_date",
    "last_activity_date",
    "plaintiff_names",
    "defendant_names",
    "attorney_names",
    "ucc_filing_number",
    "ucc_filing_type",
    "ucc_filing_date",
    "debtor_name",
    "secured_party_name",
    "keyword_hits",
    "compliance_flags",
    "exclusion_reason",
    "source_name",
    "source_url",
    "source_captured_at",
    "created_at",
    "updated_at",
]

FORM_LEAD_COLUMNS = [
    "form_lead_id",
    "grade",
    "score",
    "status",
    "created_at",
    "state",
    "business_name",
    "contact_name",
    "email",
    "phone",
    "preferred_contact_method",
    "legal_issue_type",
    "has_been_sued",
    "case_state",
    "case_county",
    "case_number",
    "mca_funder_names",
    "daily_weekly_payment_amount",
    "total_mca_balance_range",
    "bank_account_frozen",
    "ucc_lien_issue",
    "court_deadline_date",
    "has_attorney",
    "consent_to_contact",
    "consented_at",
    "consent_text",
    "page_url",
    "source_campaign",
]

GRADE_SORT = {
    "A_PLUS": 6,
    "A": 5,
    "B": 4,
    "C": 3,
    "D": 2,
    "EXCLUDE": 1,
}


def export_signals_bytes(
    session: Session,
    *,
    filters: ExportFilters,
    export_format: ExportFormat,
) -> ExportResult:
    timestamp = datetime.now(UTC)
    rows, omitted_counts = load_public_signal_export_rows(session, filters)
    content = _render_export(
        headers=PUBLIC_SIGNAL_COLUMNS,
        rows=rows,
        export_type="signals",
        export_format=export_format,
        export_timestamp=timestamp,
        filters=filters,
        omitted_counts=omitted_counts,
    )
    return ExportResult(
        content=content,
        filename=build_export_filename("mca_signals", filters, export_format, timestamp),
        media_type=_media_type(export_format),
        row_count=len(rows),
        export_timestamp=timestamp,
        filters=filters,
        omitted_counts=omitted_counts,
    )


def export_form_leads_bytes(
    session: Session,
    *,
    filters: ExportFilters,
    export_format: ExportFormat,
) -> ExportResult:
    timestamp = datetime.now(UTC)
    rows, omitted_counts = load_form_lead_export_rows(session, filters)
    content = _render_export(
        headers=FORM_LEAD_COLUMNS,
        rows=rows,
        export_type="form-leads",
        export_format=export_format,
        export_timestamp=timestamp,
        filters=filters,
        omitted_counts=omitted_counts,
    )
    return ExportResult(
        content=content,
        filename=build_export_filename("mca_form_leads", filters, export_format, timestamp),
        media_type=_media_type(export_format),
        row_count=len(rows),
        export_timestamp=timestamp,
        filters=filters,
        omitted_counts=omitted_counts,
    )


def load_public_signal_export_rows(
    session: Session,
    filters: ExportFilters,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    base_filters = replace(filters, include_suppressed=True, include_excluded=True)
    signals = [
        signal
        for signal in session.scalars(_signal_statement(base_filters)).all()
        if _matches_signal_filters(signal, filters)
    ]
    omitted_counts = _omitted_counts(signals, filters)
    filtered_signals = [
        signal for signal in signals if _is_exportable_signal(signal, filters)
    ]
    filtered_signals.sort(key=_signal_sort_key, reverse=True)
    return signals_to_export_rows(session, filtered_signals), omitted_counts


def load_form_lead_export_rows(
    session: Session,
    filters: ExportFilters,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    base_filters = replace(filters, include_suppressed=True, include_excluded=True)
    form_leads = [
        form_lead
        for form_lead in session.scalars(_form_lead_statement(base_filters)).all()
        if _matches_form_lead_filters(form_lead, filters)
    ]
    omitted_counts = _form_lead_omitted_counts(form_leads, filters)
    filtered_form_leads = [
        form_lead
        for form_lead in form_leads
        if _is_exportable_form_lead_status(form_lead, filters)
    ]
    filtered_form_leads.sort(key=_form_lead_sort_key, reverse=True)
    return form_leads_to_export_rows(session, filtered_form_leads), omitted_counts


def signals_to_export_rows(
    session: Session,
    signals: list[LeadSignal],
) -> list[dict[str, object]]:
    return [_signal_row(session, signal) for signal in signals]


def form_leads_to_export_rows(
    session: Session,
    form_leads: list[FormLead],
) -> list[dict[str, object]]:
    return [_form_lead_row(session, form_lead) for form_lead in form_leads]


def build_export_filename(
    prefix: str,
    filters: ExportFilters,
    export_format: ExportFormat,
    timestamp: datetime,
) -> str:
    state_label = "_".join(filters.states) if filters.states else "ALL"
    value_label = "A_PLUS_A" if filters.only_high_value else (filters.grade or "ALL")
    stamp = timestamp.strftime("%Y-%m-%d_%H%M%S")
    return f"{prefix}_{state_label}_{value_label}_{stamp}.{export_format}"


def _signal_statement(filters: ExportFilters) -> Select[tuple[LeadSignal]]:
    statement = select(LeadSignal)
    if filters.states:
        statement = statement.where(LeadSignal.state.in_(filters.states))
    if filters.county:
        statement = statement.where(LeadSignal.county.ilike(f"%{filters.county}%"))
    if filters.only_high_value:
        statement = statement.where(
            LeadSignal.grade.in_((LeadSignalGrade.A_PLUS, LeadSignalGrade.A))
        )
    elif filters.grade:
        statement = statement.where(LeadSignal.grade == LeadSignalGrade(filters.grade))
    if filters.min_score is not None:
        statement = statement.where(LeadSignal.score >= filters.min_score)
    if filters.signal_type:
        statement = statement.where(LeadSignal.signal_type == SignalType(filters.signal_type))
    if filters.funder_name:
        statement = statement.where(LeadSignal.funder_name.ilike(f"%{filters.funder_name}%"))
    if filters.date_from:
        statement = statement.where(LeadSignal.signal_date >= filters.date_from)
    if filters.date_to:
        statement = statement.where(LeadSignal.signal_date <= filters.date_to)
    if filters.status:
        statement = statement.where(LeadSignal.status == LeadSignalStatus(filters.status))
    return statement


def _form_lead_statement(filters: ExportFilters) -> Select[tuple[FormLead]]:
    statement = select(FormLead)
    if filters.states:
        statement = statement.where(FormLead.state.in_(filters.states))
    if filters.county:
        statement = statement.where(FormLead.case_county.ilike(f"%{filters.county}%"))
    if filters.only_high_value:
        statement = statement.where(FormLead.grade.in_((LeadSignalGrade.A_PLUS, LeadSignalGrade.A)))
    elif filters.grade:
        statement = statement.where(FormLead.grade == LeadSignalGrade(filters.grade))
    if filters.min_score is not None:
        statement = statement.where(FormLead.score >= filters.min_score)
    if filters.date_from:
        statement = statement.where(func.date(FormLead.created_at) >= filters.date_from)
    if filters.date_to:
        statement = statement.where(func.date(FormLead.created_at) <= filters.date_to)
    if filters.status:
        statement = statement.where(FormLead.status == filters.status)
    return statement


def _matches_signal_filters(signal: LeadSignal, filters: ExportFilters) -> bool:
    if filters.states and signal.state not in filters.states:
        return False
    if filters.county and filters.county.lower() not in (signal.county or "").lower():
        return False
    if filters.only_high_value and signal.grade not in (LeadSignalGrade.A_PLUS, LeadSignalGrade.A):
        return False
    if filters.grade and signal.grade != LeadSignalGrade(filters.grade):
        return False
    if filters.min_score is not None and signal.score < filters.min_score:
        return False
    if filters.signal_type and signal.signal_type != SignalType(filters.signal_type):
        return False
    if filters.funder_name:
        funder_filter = filters.funder_name.lower()
        if funder_filter not in (signal.funder_name or "").lower():
            return False
    if filters.date_from and signal.signal_date < filters.date_from:
        return False
    if filters.date_to and signal.signal_date > filters.date_to:
        return False
    return not filters.status or signal.status == LeadSignalStatus(filters.status)


def _matches_form_lead_filters(form_lead: FormLead, filters: ExportFilters) -> bool:
    if filters.states and form_lead.state not in filters.states:
        return False
    if filters.county and filters.county.lower() not in (form_lead.case_county or "").lower():
        return False
    if filters.only_high_value and form_lead.grade not in (
        LeadSignalGrade.A_PLUS,
        LeadSignalGrade.A,
    ):
        return False
    if filters.grade and form_lead.grade != LeadSignalGrade(filters.grade):
        return False
    if filters.min_score is not None and form_lead.score < filters.min_score:
        return False
    if filters.funder_name and not any(
        filters.funder_name.lower() in funder.lower() for funder in form_lead.mca_funder_names
    ):
        return False
    created_date = form_lead.created_at.date() if form_lead.created_at else None
    if filters.date_from and created_date and created_date < filters.date_from:
        return False
    if filters.date_to and created_date and created_date > filters.date_to:
        return False
    return not filters.status or form_lead.status == filters.status


def _signal_row(session: Session, signal: LeadSignal) -> dict[str, object]:
    source = session.get(Source, signal.source_id)
    case = session.get(Case, signal.case_id) if signal.case_id else None
    ucc = session.get(UccFiling, signal.ucc_filing_id) if signal.ucc_filing_id else None
    raw_artifact = _source_raw_artifact(session, case=case, ucc=ucc)
    keyword_hits = _keyword_hits(session, case=case, ucc=ucc)
    return {
        "signal_id": str(signal.id),
        "grade": signal.grade.value,
        "score": signal.score,
        "risk_score": signal.risk_score,
        "status": signal.status.value,
        "signal_type": signal.signal_type.value,
        "signal_date": _date_value(signal.signal_date),
        "state": signal.state,
        "county": signal.county,
        "business_name": public_export_value(signal.business_name),
        "normalized_business_name": signal.normalized_business_name,
        "funder_name": public_export_value(signal.funder_name),
        "title": public_export_value(signal.title),
        "summary": public_export_value(signal.summary),
        "case_number": public_export_value(case.case_number if case else None),
        "court_name": case.court_name if case else None,
        "case_type": case.case_type if case else None,
        "filing_date": _date_value(case.filing_date if case else None),
        "last_activity_date": _date_value(case.last_activity_date if case else None),
        "plaintiff_names": [public_export_value(name) for name in case.plaintiff_names]
        if case
        else [],
        "defendant_names": [public_export_value(name) for name in case.defendant_names]
        if case
        else [],
        "attorney_names": [public_export_value(name) for name in case.attorney_names]
        if case
        else [],
        "ucc_filing_number": public_export_value(ucc.filing_number if ucc else None),
        "ucc_filing_type": ucc.filing_type if ucc else None,
        "ucc_filing_date": _date_value(ucc.filing_date if ucc else None),
        "debtor_name": public_export_value(ucc.debtor_name if ucc else None),
        "secured_party_name": public_export_value(ucc.secured_party_name if ucc else None),
        "keyword_hits": keyword_hits,
        "compliance_flags": signal.compliance_flags,
        "exclusion_reason": public_export_value(signal.exclusion_reason),
        "source_name": source.name if source else None,
        "source_url": signal.source_url,
        "source_captured_at": _datetime_value(raw_artifact.captured_at if raw_artifact else None),
        "created_at": _datetime_value(signal.created_at),
        "updated_at": _datetime_value(signal.updated_at),
    }


def _form_lead_row(session: Session, form_lead: FormLead) -> dict[str, object]:
    consent_event = _consent_event(session, form_lead)
    consented_at = consent_event.consented_at if consent_event else None
    contact_name = consented_form_value(form_lead, form_lead.contact_name)
    email = consented_form_value(form_lead, form_lead.email)
    phone = consented_form_value(form_lead, form_lead.phone)
    consent_text = (
        public_export_value(form_lead.consent_text)
        if form_lead.consent_to_contact
        else NO_CONSENT_REDACTED
    )
    return {
        "form_lead_id": str(form_lead.id),
        "grade": form_lead.grade.value,
        "score": form_lead.score,
        "status": form_lead.status,
        "created_at": _datetime_value(form_lead.created_at),
        "state": form_lead.state,
        "business_name": public_export_value(form_lead.business_name),
        "contact_name": contact_name,
        "email": email,
        "phone": phone,
        "preferred_contact_method": form_lead.preferred_contact_method,
        "legal_issue_type": form_lead.legal_issue_type,
        "has_been_sued": form_lead.has_been_sued,
        "case_state": form_lead.case_state,
        "case_county": form_lead.case_county,
        "case_number": public_export_value(form_lead.case_number),
        "mca_funder_names": [public_export_value(name) for name in form_lead.mca_funder_names],
        "daily_weekly_payment_amount": _decimal_value(form_lead.daily_weekly_payment_amount),
        "total_mca_balance_range": form_lead.total_mca_balance_range,
        "bank_account_frozen": form_lead.bank_account_frozen,
        "ucc_lien_issue": form_lead.ucc_lien_issue,
        "court_deadline_date": _date_value(form_lead.court_deadline_date),
        "has_attorney": form_lead.has_attorney,
        "consent_to_contact": form_lead.consent_to_contact,
        "consented_at": _datetime_value(consented_at),
        "consent_text": consent_text,
        "page_url": form_lead.page_url,
        "source_campaign": form_lead.source_campaign,
    }


def _render_export(
    *,
    headers: list[str],
    rows: list[dict[str, object]],
    export_type: ExportType,
    export_format: ExportFormat,
    export_timestamp: datetime,
    filters: ExportFilters,
    omitted_counts: dict[str, int],
) -> bytes:
    if export_format == "csv":
        return rows_to_csv(headers, rows)
    return rows_to_xlsx(
        headers=headers,
        rows=rows,
        export_type=export_type,
        export_timestamp=export_timestamp,
        filters=filters,
        omitted_counts=omitted_counts,
    )


def _media_type(export_format: ExportFormat) -> str:
    return CSV_MEDIA_TYPE if export_format == "csv" else XLSX_MEDIA_TYPE


def _omitted_counts(signals: list[LeadSignal], filters: ExportFilters) -> dict[str, int]:
    return {
        "excluded": 0
        if filters.include_excluded
        else sum(_is_excluded_signal(signal) for signal in signals),
        "suppressed": 0
        if filters.include_suppressed
        else sum(signal.status == LeadSignalStatus.SUPPRESSED for signal in signals),
    }


def _form_lead_omitted_counts(form_leads: list[FormLead], filters: ExportFilters) -> dict[str, int]:
    return {
        "excluded": 0
        if filters.include_excluded
        else sum(_is_excluded_form_lead(form_lead) for form_lead in form_leads),
        "suppressed": 0
        if filters.include_suppressed
        else sum(form_lead.status == "suppressed" for form_lead in form_leads),
    }


def _is_exportable_signal(signal: LeadSignal, filters: ExportFilters) -> bool:
    if not filters.include_suppressed and signal.status == LeadSignalStatus.SUPPRESSED:
        return False
    return filters.include_excluded or not _is_excluded_signal(signal)


def _is_exportable_form_lead_status(form_lead: FormLead, filters: ExportFilters) -> bool:
    if not filters.include_suppressed and form_lead.status == "suppressed":
        return False
    return filters.include_excluded or not _is_excluded_form_lead(form_lead)


def _is_excluded_signal(signal: LeadSignal) -> bool:
    return signal.status == LeadSignalStatus.EXCLUDED or signal.grade == LeadSignalGrade.EXCLUDE


def _is_excluded_form_lead(form_lead: FormLead) -> bool:
    return form_lead.status == "excluded" or form_lead.grade == LeadSignalGrade.EXCLUDE


def _signal_sort_key(signal: LeadSignal) -> tuple[int, int, object]:
    return (GRADE_SORT[signal.grade.value], signal.score, signal.signal_date)


def _form_lead_sort_key(form_lead: FormLead) -> tuple[int, int, object]:
    return (GRADE_SORT[form_lead.grade.value], form_lead.score, form_lead.created_at)


def _source_raw_artifact(
    session: Session,
    *,
    case: Case | None,
    ucc: UccFiling | None,
) -> RawArtifact | None:
    raw_artifact_id = case.raw_artifact_id if case else ucc.raw_artifact_id if ucc else None
    return session.get(RawArtifact, raw_artifact_id) if raw_artifact_id else None


def _keyword_hits(session: Session, *, case: Case | None, ucc: UccFiling | None) -> list[str]:
    if case:
        documents = session.scalars(select(CaseDocument).where(CaseDocument.case_id == case.id))
        hits: list[str] = []
        for document in documents:
            hits.extend(document.keyword_hits)
        return list(dict.fromkeys(hits))
    if ucc:
        return list(classify_text(ucc.collateral_text).keyword_hits)
    return []


def _consent_event(session: Session, form_lead: FormLead) -> ConsentEvent | None:
    if not form_lead.consent_to_contact:
        return None
    return session.scalar(
        select(ConsentEvent)
        .where(ConsentEvent.form_lead_id == str(form_lead.id))
        .order_by(ConsentEvent.consented_at.desc())
    )


def _date_value(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _datetime_value(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _decimal_value(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
