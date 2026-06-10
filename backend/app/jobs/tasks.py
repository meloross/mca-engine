from __future__ import annotations

import asyncio
import time
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.compliance import normalize_business_name
from app.config import settings
from app.db import SessionLocal
from app.enrichment import enrich_lead
from app.events import publish_event, signal_event_payload
from app.exports import ExportFilters, export_signals_bytes
from app.ids import next_batch_number, next_lead_reference_id
from app.integrations.google_sheets import GoogleSheetsSyncService
from app.models import (
    AccessMethod,
    AuditLog,
    EnrichmentStatus,
    LeadSignal,
    LeadSignalGrade,
    LeadSignalStatus,
    SignalType,
    Source,
    SourceType,
)
from app.scoring import score_signal
from app.services.fl_importer import import_mock_fl_to_db
from app.services.ny_importer import import_mock_ny_to_db
from app.services.presentation import analytics_summary


def record_worker_heartbeat() -> None:
    _heartbeat("worker")


def record_scheduler_heartbeat() -> None:
    _heartbeat("scheduler")


def process_pending_enrichment_jobs(limit: int = 50) -> dict[str, int]:
    with SessionLocal() as session:
        grades = {grade.strip() for grade in settings.enrichment_grades.split(",") if grade.strip()}
        statement = (
            select(LeadSignal)
            .where(
                LeadSignal.enrichment_status == EnrichmentStatus.PENDING,
                LeadSignal.score >= settings.enrichment_min_score,
                LeadSignal.grade.in_([LeadSignalGrade(grade) for grade in grades]),
            )
            .order_by(LeadSignal.created_at.asc())
            .limit(limit)
        )
        signals = list(session.scalars(statement).all())
        for signal in signals:
            asyncio.run(enrich_lead(session, signal.lead_reference_id))
        return {"attempted": len(signals)}


def enrich_single_lead(lead_reference_id: str, *, force: bool = False) -> dict[str, object]:
    with SessionLocal() as session:
        return asyncio.run(enrich_lead(session, lead_reference_id, force=force))


def sync_google_sheets_job() -> dict[str, object]:
    with SessionLocal() as session:
        results = GoogleSheetsSyncService(session).sync_all_to_master_sheet()
        return {key: result.appended for key, result in results.items()}


def refresh_analytics_dashboard_summary() -> dict[str, object]:
    with SessionLocal() as session:
        summary = analytics_summary(session)
        session.add(
            AuditLog(
                actor="scheduler",
                action="analytics_summary_refreshed",
                entity_type="analytics",
                entity_id="summary",
                event_metadata=summary,
            )
        )
        session.commit()
        return summary


def run_live_sources_job(state: str | None = None) -> dict[str, object]:
    if not settings.enable_live_adapters:
        return {"status": "skipped", "reason": "ENABLE_LIVE_ADAPTERS=false"}
    normalized_state = state.upper() if state else "ALL"
    return {"status": "skipped", "state": normalized_state, "reason": "No live adapters enabled."}


def run_mock_ingestion_job(state: str = "NY") -> dict[str, int | str]:
    with SessionLocal() as session:
        if state.upper() == "FL":
            result = asyncio.run(import_mock_fl_to_db(session))
            return {"state": "FL", **result}
        result = asyncio.run(import_mock_ny_to_db(session))
        return {"state": "NY", **result}


def export_daily_high_value_job() -> dict[str, object]:
    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)
    with SessionLocal() as session:
        filters = ExportFilters.from_state(states=("NY", "FL"), only_high_value=True)
        csv_result = export_signals_bytes(session, filters=filters, export_format="csv")
        xlsx_result = export_signals_bytes(session, filters=filters, export_format="xlsx")
        csv_path = output_dir / csv_result.filename
        xlsx_path = output_dir / xlsx_result.filename
        csv_path.write_bytes(csv_result.content)
        xlsx_path.write_bytes(xlsx_result.content)
        return {
            "csv": str(csv_path),
            "xlsx": str(xlsx_path),
            "rows": csv_result.row_count,
        }


def create_daily_batch_summary() -> dict[str, object]:
    with SessionLocal() as session:
        today = date.today()
        count = session.scalar(
            select(func.count()).select_from(LeadSignal).where(LeadSignal.batch_date == today)
        )
        return {"batch_date": today.isoformat(), "signals": int(count or 0)}


def create_demo_leads(count: int = 10, interval_seconds: int = 0) -> dict[str, int]:
    created = 0
    for index in range(count):
        with SessionLocal() as session:
            signal = _insert_demo_signal(session, index)
            publish_event("signal_created", signal_event_payload(signal))
            session.commit()
            created += 1
            asyncio.run(enrich_lead(session, signal.lead_reference_id))
        if interval_seconds > 0 and index < count - 1:
            time.sleep(interval_seconds)
    return {"created": created}


def _insert_demo_signal(session: Session, index: int) -> LeadSignal:
    state = "NY" if index % 2 == 0 else "FL"
    source = session.scalar(
        select(Source).where(Source.name == "Live Demo Lead Generator", Source.state == state)
    )
    if source is None:
        source = Source(
            name="Live Demo Lead Generator",
            state=state,
            source_type=SourceType.MANUAL_UPLOAD,
            base_url="https://demo.local/live",
            access_method=AccessMethod.MOCK,
            terms_notes="Synthetic live demo source.",
            automation_allowed=True,
            requires_login=False,
            requires_payment=False,
        )
        session.add(source)
        session.flush()
    business = f"Live Demo Merchant {datetime.now(UTC):%H%M%S}-{index:02d} LLC"
    funder = "Cloudfund"
    signal_date = date.today()
    record = {
        "signal_type": SignalType.LITIGATION_NEW_CASE.value,
        "business_name": business,
        "caption": f"{funder} LLC v. {business}",
        "document_text": "Merchant cash advance default, daily ACH, and UCC lien.",
        "plaintiff_names": [funder],
        "defendant_names": [business],
        "filing_date": signal_date,
        "source_automation_allowed": True,
    }
    score = score_signal(record, as_of=signal_date)
    signal = LeadSignal(
        lead_reference_id=next_lead_reference_id(session, state, signal_date),
        batch_number=next_batch_number(session, "MOCK", signal_date),
        batch_date=signal_date,
        source_category=source.source_type.value,
        source_name=source.name,
        source_captured_at=datetime.now(UTC),
        signal_type=SignalType.LITIGATION_NEW_CASE,
        state=state,
        county="Kings" if state == "NY" else "Miami-Dade",
        business_name=business,
        normalized_business_name=normalize_business_name(business),
        funder_name=funder,
        signal_date=signal_date,
        title=f"Live demo MCA signal: {business}",
        summary="Synthetic live dashboard lead.",
        score=score.score,
        risk_score=score.risk_score,
        grade=LeadSignalGrade(score.grade),
        status=LeadSignalStatus.NEW,
        compliance_flags=["mock", "live_demo"],
        source_id=source.id,
        source_url=f"https://demo.local/live/{business.replace(' ', '-')}",
    )
    session.add(signal)
    session.flush()
    return signal


def _heartbeat(kind: str) -> None:
    with SessionLocal() as session:
        session.add(
            AuditLog(
                actor=kind,
                action=f"{kind}_heartbeat",
                entity_type="service",
                entity_id=kind,
                event_metadata={"timestamp": datetime.now(UTC).isoformat()},
            )
        )
        session.commit()
