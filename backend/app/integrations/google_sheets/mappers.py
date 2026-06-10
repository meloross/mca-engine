from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.models import EnrichmentAttempt, FormLead, IngestionRun, LeadDelivery, LeadSignal, Source

NO_CONSENT_REDACTION = "[REDACTED - NO CONSENT]"


def map_lead_signal_to_master_row(lead_signal: LeadSignal) -> list[str]:
    case = _related(lead_signal, "case")
    ucc = _related(lead_signal, "ucc")
    delivery = _related(lead_signal, "delivery")
    buyer = _related(lead_signal, "buyer")
    return [
        _string(lead_signal.lead_reference_id),
        _string(lead_signal.batch_number),
        _date(lead_signal.batch_date),
        _enum(lead_signal.signal_type),
        _string(lead_signal.state),
        _string(lead_signal.county),
        _string(lead_signal.business_name),
        _string(lead_signal.normalized_business_name),
        _string(lead_signal.funder_name),
        _date(lead_signal.signal_date),
        _enum(lead_signal.grade),
        _string(lead_signal.score),
        _string(lead_signal.risk_score),
        _enum(lead_signal.status),
        _string(lead_signal.source_category),
        _string(lead_signal.source_name),
        _string(lead_signal.source_url),
        _datetime(lead_signal.source_captured_at),
        _string(getattr(case, "case_number", None)),
        _string(getattr(case, "court_name", None)),
        _string(getattr(case, "case_type", None)),
        _date(getattr(case, "filing_date", None)),
        _string(getattr(ucc, "filing_number", None)),
        _string(getattr(ucc, "filing_type", None)),
        _date(getattr(ucc, "filing_date", None)),
        _list(_related(lead_signal, "keyword_hits")),
        _list(lead_signal.compliance_flags),
        _string(lead_signal.exclusion_reason),
        _string(getattr(buyer, "firm_name", None)),
        _datetime(getattr(delivery, "delivered_at", None)),
        _enum(getattr(delivery, "delivery_method", None)),
        _buyer_status(delivery),
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        _string(lead_signal.summary),
        _datetime(lead_signal.created_at),
        _datetime(lead_signal.updated_at),
        _string(lead_signal.owner_principal_name),
        _string(lead_signal.owner_principal_title),
        _string(lead_signal.owner_source),
        _string(lead_signal.registered_agent_name),
        _string(lead_signal.business_phone),
        _string(lead_signal.phone_source),
        _string(lead_signal.business_email),
        _string(lead_signal.email_source),
        _string(lead_signal.business_website),
        _string(lead_signal.google_place_id),
        _string(lead_signal.google_maps_url),
        _enum(lead_signal.enrichment_status),
        _string(lead_signal.enrichment_confidence),
        _list(lead_signal.enrichment_sources),
        _datetime(lead_signal.enriched_at),
        _string(lead_signal.do_not_contact),
    ]


def map_ingestion_run_to_batch_log_row(ingestion_run: IngestionRun) -> list[str]:
    source = _related(ingestion_run, "source") or getattr(ingestion_run, "source", None)
    return [
        _string(ingestion_run.batch_number),
        _date(ingestion_run.batch_date),
        _string(getattr(source, "state", None)),
        _enum(getattr(source, "source_type", None)),
        _string(getattr(source, "name", None)),
        _string(ingestion_run.import_mode or ingestion_run.run_type),
        _string(ingestion_run.adapter_name),
        _string(ingestion_run.query_filter_used),
        _string(ingestion_run.raw_artifact_path),
        _string(ingestion_run.raw_artifact_hash),
        _string(ingestion_run.records_seen),
        _string(ingestion_run.records_created),
        _string(ingestion_run.records_updated),
        _string(getattr(ingestion_run, "_sheet_signals_created", ingestion_run.records_created)),
        _string(getattr(ingestion_run, "_sheet_excluded_count", "")),
        _datetime(ingestion_run.started_at),
        _datetime(ingestion_run.finished_at),
        _string(ingestion_run.operator),
        _string(ingestion_run.status),
        _string(ingestion_run.notes),
    ]


def map_source_to_source_registry_row(source: Source) -> list[str]:
    return [
        _string(source.id),
        _string(source.state),
        _enum(source.source_type),
        _string(source.name),
        _string(source.base_url),
        _enum(source.access_method),
        _string(source.automation_allowed),
        _string(source.requires_login),
        _string(source.requires_payment),
        _string(source.terms_notes),
        _string(source.terms_notes),
        "true",
        _datetime(source.updated_at or source.created_at),
    ]


def map_delivery_to_delivery_log_row(lead_delivery: LeadDelivery) -> list[str]:
    lead = _related(lead_delivery, "lead")
    buyer = _related(lead_delivery, "buyer")
    return [
        _string(lead_delivery.delivery_id),
        _string(getattr(lead, "lead_reference_id", None)),
        _string(lead_delivery.batch_number),
        _string(getattr(buyer, "firm_name", None)),
        _string(getattr(buyer, "contact_name", None)),
        _enum(lead_delivery.delivery_method),
        _datetime(lead_delivery.delivered_at),
        _string(lead_delivery.accepted),
        _string(lead_delivery.rejected_reason),
        "",
        "",
        _delivery_status(lead_delivery),
        "",
    ]


def map_form_lead_to_opt_in_row(form_lead: FormLead) -> list[str]:
    contact_name = _consented_value(form_lead, form_lead.contact_name)
    email = _consented_value(form_lead, form_lead.email)
    phone = _consented_value(form_lead, form_lead.phone)
    consent_text = form_lead.consent_text if form_lead.consent_to_contact else NO_CONSENT_REDACTION
    return [
        _string(form_lead.form_lead_ref_id),
        _string(form_lead.linked_lead_reference_id),
        _string(form_lead.batch_number),
        _string(form_lead.state),
        _string(form_lead.business_name),
        _string(contact_name),
        _string(email),
        _string(phone),
        _string(form_lead.preferred_contact_method),
        _string(form_lead.legal_issue_type),
        _string(form_lead.has_been_sued),
        _string(form_lead.case_state),
        _string(form_lead.case_county),
        _string(form_lead.case_number),
        _list(form_lead.mca_funder_names),
        _string(form_lead.daily_weekly_payment_amount),
        _string(form_lead.total_mca_balance_range),
        _string(form_lead.bank_account_frozen),
        _string(form_lead.ucc_lien_issue),
        _date(form_lead.court_deadline_date),
        _string(form_lead.has_attorney),
        _string(form_lead.consent_to_contact),
        _datetime(_related(form_lead, "consented_at")),
        _string(consent_text),
        _string(form_lead.page_url),
        _string(form_lead.source_campaign),
        _string(form_lead.score),
        _enum(form_lead.grade),
        _string(_related(form_lead, "routed_buyer")),
        _string(form_lead.status),
        _datetime(form_lead.created_at),
    ]


def map_enrichment_attempt_to_log_row(attempt: EnrichmentAttempt) -> list[str]:
    signal = _related(attempt, "lead")
    enrichment = _related(attempt, "enrichment")
    return [
        _string(attempt.id),
        _string(attempt.enrichment_run_id),
        _string(attempt.lead_reference_id),
        _string(getattr(signal, "batch_number", "")),
        _string(attempt.provider),
        _string(getattr(enrichment, "source_record_id", "")),
        _string(attempt.query),
        _string(getattr(enrichment, "business_address", "")),
        _string(getattr(enrichment, "business_phone", "")),
        _string(getattr(enrichment, "business_email", "")),
        _string(getattr(enrichment, "business_website", "")),
        _string(getattr(enrichment, "owner_principal_name", "")),
        _string(getattr(enrichment, "confidence", "")),
        _string(attempt.status),
        _string(attempt.error),
        _datetime(attempt.started_at),
        _datetime(attempt.finished_at),
        _string(attempt.result_summary),
    ]


def _related(record: object, name: str) -> Any:
    return getattr(record, f"_sheet_{name}", None)


def _enum(value: object) -> str:
    return _string(getattr(value, "value", value))


def _list(values: object) -> str:
    if not values:
        return ""
    if isinstance(values, (list, tuple, set)):
        return "; ".join(_string(value) for value in values)
    return _string(values)


def _date(value: object) -> str:
    return value.isoformat() if isinstance(value, date) else ""


def _datetime(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else ""


def _string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _buyer_status(delivery: object | None) -> str:
    if delivery is None:
        return ""
    accepted = getattr(delivery, "accepted", None)
    if accepted is True:
        return "accepted"
    if accepted is False:
        return "rejected"
    return "delivered"


def _delivery_status(delivery: LeadDelivery) -> str:
    if delivery.accepted is True:
        return "accepted"
    if delivery.accepted is False:
        return "rejected"
    return "delivered"


def _consented_value(form_lead: FormLead, value: object) -> object:
    return value if form_lead.consent_to_contact else NO_CONSENT_REDACTION
