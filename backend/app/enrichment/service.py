from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.enrichment.base import EnrichmentProvider, EnrichmentResult, LeadContactCandidate
from app.enrichment.matching import normalize_contact_value
from app.enrichment.providers import (
    FloridaSunbizProvider,
    GooglePlacesProvider,
    MockEnrichmentProvider,
    NewYorkBusinessRegistryProvider,
    WebsiteCrawlerProvider,
)
from app.events import publish_event
from app.integrations.google_sheets import GoogleSheetsSyncService
from app.models import (
    BusinessEnrichment,
    ContactVerificationStatus,
    EnrichmentAttempt,
    EnrichmentRun,
    EnrichmentStatus,
    LeadContact,
    LeadContactType,
    LeadSignal,
    LeadSignalStatus,
)


async def enrich_lead(
    session: Session,
    lead_reference_id: str,
    *,
    force: bool = False,
    providers: list[EnrichmentProvider] | None = None,
) -> dict[str, object]:
    signal = session.scalar(
        select(LeadSignal).where(LeadSignal.lead_reference_id == lead_reference_id)
    )
    if signal is None:
        raise LookupError(f"Lead signal {lead_reference_id} not found.")
    if not force and signal.status in {LeadSignalStatus.SUPPRESSED, LeadSignalStatus.EXCLUDED}:
        signal.enrichment_status = EnrichmentStatus.SKIPPED
        session.commit()
        return {"lead_reference_id": lead_reference_id, "status": "skipped"}

    publish_event(
        "enrichment_started",
        {"lead_reference_id": signal.lead_reference_id, "business_name": signal.business_name},
    )
    run = EnrichmentRun(
        enrichment_run_id=f"ENR-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}",
        batch_number=signal.batch_number,
        provider="orchestrator",
        status="running",
        records_attempted=1,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    session.flush()

    results: list[EnrichmentResult] = []
    for provider in providers or _default_providers(session):
        result = await _run_provider(session, run.enrichment_run_id, provider, signal)
        results.append(result)
        _store_business_enrichment(session, signal, result)
        for contact in result.contacts:
            _store_contact(session, signal, contact)
        _apply_result(signal, result)
        session.flush()
        if signal.business_website and provider.name != "website_crawler":
            continue

    _finalize_signal(signal, results)
    _finalize_run(run, results)
    session.commit()
    payload = _enrichment_event_payload(signal)
    publish_event("enrichment_completed", payload)
    if settings.google_sheets_enabled:
        GoogleSheetsSyncService(session).sync_new_leads_to_master_sheet()
        publish_event("google_sheet_synced", {"lead_reference_id": signal.lead_reference_id})
    return payload


def _default_providers(session: Session) -> list[EnrichmentProvider]:
    return [
        FloridaSunbizProvider(session),
        NewYorkBusinessRegistryProvider(),
        GooglePlacesProvider(),
        WebsiteCrawlerProvider(),
        MockEnrichmentProvider(),
    ]


async def _run_provider(
    session: Session,
    enrichment_run_id: str,
    provider: EnrichmentProvider,
    signal: LeadSignal,
) -> EnrichmentResult:
    started_at = datetime.now(UTC)
    try:
        result = await provider.enrich(signal)
    except Exception as exc:
        result = EnrichmentResult(
            provider=provider.name,
            status="failed",
            error=str(exc),
        )
    session.add(
        EnrichmentAttempt(
            enrichment_run_id=enrichment_run_id,
            lead_reference_id=signal.lead_reference_id,
            provider=provider.name,
            query=signal.business_name,
            status=result.status,
            result_summary=_result_summary(result),
            error=result.error,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
    )
    return result


def _store_business_enrichment(
    session: Session,
    signal: LeadSignal,
    result: EnrichmentResult,
) -> None:
    session.add(
        BusinessEnrichment(
            lead_signal_id=signal.id,
            lead_reference_id=signal.lead_reference_id,
            normalized_business_name=signal.normalized_business_name,
            state=signal.state,
            county=signal.county,
            source_provider=result.provider,
            source_record_id=result.source_record_id,
            google_place_id=result.google_place_id,
            google_maps_url=result.google_maps_url,
            business_website=result.business_website,
            business_phone=result.business_phone,
            business_email=result.business_email,
            owner_principal_name=result.owner_principal_name,
            owner_principal_title=result.owner_principal_title,
            registered_agent_name=result.registered_agent_name,
            registered_agent_address=result.registered_agent_address,
            business_address=result.business_address,
            confidence=result.confidence,
            status=EnrichmentStatus(result.status),
            error=result.error,
            source_url=result.source_url,
            enriched_at=datetime.now(UTC),
        )
    )


def _store_contact(
    session: Session,
    signal: LeadSignal,
    candidate: LeadContactCandidate,
) -> None:
    normalized_value = normalize_contact_value(candidate.value)
    existing = session.scalar(
        select(LeadContact).where(
            LeadContact.lead_reference_id == signal.lead_reference_id,
            LeadContact.contact_type == LeadContactType(candidate.contact_type),
            LeadContact.normalized_value == normalized_value,
        )
    )
    if existing is not None:
        if candidate.confidence > existing.confidence:
            existing.confidence = candidate.confidence
            existing.source_provider = candidate.source_provider
            existing.source_url = candidate.source_url
        return
    session.add(
        LeadContact(
            lead_signal_id=signal.id,
            lead_reference_id=signal.lead_reference_id,
            contact_type=LeadContactType(candidate.contact_type),
            value=candidate.value,
            normalized_value=normalized_value,
            source_provider=candidate.source_provider,
            source_url=candidate.source_url,
            source_category=candidate.source_category,
            confidence=candidate.confidence,
            verification_status=ContactVerificationStatus(candidate.verification_status),
            is_opt_in=candidate.is_opt_in,
            contact_consent=candidate.contact_consent,
            contact_allowed=candidate.contact_allowed,
            do_not_contact=candidate.do_not_contact,
            found_at=datetime.now(UTC),
        )
    )


def _apply_result(signal: LeadSignal, result: EnrichmentResult) -> None:
    if result.owner_principal_name and not signal.owner_principal_name:
        signal.owner_principal_name = result.owner_principal_name
        signal.owner_principal_title = result.owner_principal_title
        signal.owner_source = result.provider
    if result.registered_agent_name and not signal.registered_agent_name:
        signal.registered_agent_name = result.registered_agent_name
    if result.business_phone and not signal.business_phone:
        signal.business_phone = result.business_phone
        signal.phone_source = result.provider
    if result.business_email and not signal.business_email:
        signal.business_email = result.business_email
        signal.email_source = result.provider
    if result.business_website and not signal.business_website:
        signal.business_website = result.business_website
    if result.google_place_id and not signal.google_place_id:
        signal.google_place_id = result.google_place_id
        signal.google_maps_url = result.google_maps_url
    should_track_source = (
        result.status not in {"skipped", "failed"}
        and result.provider not in signal.enrichment_sources
    )
    if should_track_source:
        signal.enrichment_sources = [*signal.enrichment_sources, result.provider]


def _finalize_signal(signal: LeadSignal, results: list[EnrichmentResult]) -> None:
    successes = [result for result in results if result.status == "success"]
    partials = [result for result in results if result.status == "partial"]
    failures = [result for result in results if result.status == "failed"]
    if successes:
        signal.enrichment_status = EnrichmentStatus.SUCCESS
    elif partials:
        signal.enrichment_status = EnrichmentStatus.PARTIAL
    elif failures:
        signal.enrichment_status = EnrichmentStatus.FAILED
    else:
        signal.enrichment_status = EnrichmentStatus.SKIPPED
    signal.enrichment_confidence = max((result.confidence for result in results), default=0)
    signal.enriched_at = datetime.now(UTC)


def _finalize_run(run: EnrichmentRun, results: list[EnrichmentResult]) -> None:
    run.status = "completed"
    run.finished_at = datetime.now(UTC)
    run.records_succeeded = sum(result.status == "success" for result in results)
    run.records_partial = sum(result.status == "partial" for result in results)
    run.records_failed = sum(result.status == "failed" for result in results)
    run.notes = _result_summary(results[-1]) if results else None


def _result_summary(result: EnrichmentResult) -> str:
    found = [
        label
        for label, value in (
            ("phone", result.business_phone),
            ("email", result.business_email),
            ("website", result.business_website),
            ("owner_principal", result.owner_principal_name),
            ("registered_agent", result.registered_agent_name),
        )
        if value
    ]
    return f"{result.provider}: {result.status}; found={','.join(found) or 'none'}"


def _enrichment_event_payload(signal: LeadSignal) -> dict[str, object]:
    return {
        "lead_reference_id": signal.lead_reference_id,
        "business_name": signal.business_name,
        "owner_principal_name": signal.owner_principal_name,
        "business_phone": signal.business_phone,
        "business_email": signal.business_email,
        "business_website": signal.business_website,
        "google_place_id": signal.google_place_id,
        "enrichment_status": signal.enrichment_status.value,
        "confidence": signal.enrichment_confidence,
        "enriched_at": signal.enriched_at.isoformat() if signal.enriched_at else None,
    }
