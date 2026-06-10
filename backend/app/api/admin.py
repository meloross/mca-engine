from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.integrations.google_sheets import GoogleSheetsSyncResult, GoogleSheetsSyncService
from app.jobs.queue import enqueue_job, queue_status
from app.jobs.tasks import (
    create_demo_leads,
    process_pending_enrichment_jobs,
    sync_google_sheets_job,
)
from app.models import AuditLog, EnrichmentRun, IngestionRun, LeadSignal
from app.services.fl_importer import import_mock_fl_to_db
from app.services.ny_importer import import_mock_ny_to_db

router = APIRouter(prefix="/admin", tags=["admin"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/import/mock")
async def import_mock(
    state: Annotated[str, Query(min_length=2, max_length=2)],
    session: SessionDependency,
) -> dict[str, int | str]:
    normalized_state = state.upper()
    if normalized_state == "NY":
        result = await import_mock_ny_to_db(session)
        return {"state": "NY", **result}
    if normalized_state == "FL":
        result = await import_mock_fl_to_db(session)
        return {"state": "FL", **result}

    raise HTTPException(status_code=400, detail="Only NY and FL mock imports are implemented.")


# TODO: Replace with authenticated admin authorization before production exposure.
@router.get("/sync/google-sheets/status")
def google_sheets_sync_status(session: SessionDependency) -> dict[str, object]:
    return asdict(GoogleSheetsSyncService(session).status())


@router.post("/sync/google-sheets/all")
def sync_google_sheets_all(session: SessionDependency) -> dict[str, object]:
    return _serialize_results(GoogleSheetsSyncService(session).sync_all_to_master_sheet())


@router.post("/sync/google-sheets/leads")
def sync_google_sheets_leads(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_new_leads_to_master_sheet()
    return asdict(result)


@router.post("/sync/google-sheets/batches")
def sync_google_sheets_batches(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_batch_log_to_master_sheet()
    return asdict(result)


@router.post("/sync/google-sheets/sources")
def sync_google_sheets_sources(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_sources_to_master_sheet()
    return asdict(result)


@router.post("/sync/google-sheets/deliveries")
def sync_google_sheets_deliveries(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_delivery_log_to_master_sheet()
    return asdict(result)


@router.post("/sync/google-sheets/opt-in-leads")
def sync_google_sheets_opt_in_leads(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_opt_in_leads_to_master_sheet()
    return asdict(result)


@router.post("/sync/google-sheets/enrichment-log")
def sync_google_sheets_enrichment_log(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_enrichment_log_to_master_sheet()
    return asdict(result)


@router.get("/jobs/status")
def jobs_status(session: SessionDependency) -> dict[str, object]:
    redis_status = queue_status()
    database_ok = _database_ok(session)
    return {
        "backend_status": "ok",
        "worker_heartbeat": _last_audit(session, "worker_heartbeat"),
        "scheduler_heartbeat": _last_audit(session, "scheduler_heartbeat"),
        "redis_connection": redis_status.redis_connected,
        "database_connection": database_ok,
        "last_ingestion_run": _last_ingestion_run(session),
        "last_enrichment_run": _last_enrichment_run(session),
        "pending_jobs": redis_status.pending_jobs,
        "failed_jobs": redis_status.failed_jobs,
        "last_lead_inserted_at": _last_lead_inserted_at(session),
    }


@router.get("/jobs/recent")
def jobs_recent(session: SessionDependency) -> list[dict[str, object]]:
    events = session.scalars(
        select(AuditLog)
        .where(
            AuditLog.action.in_(
                (
                    "worker_heartbeat",
                    "scheduler_heartbeat",
                    "analytics_summary_refreshed",
                    "google_sheets_sync_success",
                    "google_sheets_sync_error",
                )
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(25)
    ).all()
    return [
        {
            "action": event.action,
            "actor": event.actor,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "metadata": event.event_metadata,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in events
    ]


@router.get("/jobs/queues")
def jobs_queues() -> dict[str, object]:
    status = queue_status()
    return asdict(status)


@router.post("/jobs/enqueue/demo-leads")
def enqueue_demo_leads(count: int = 10, interval_seconds: int = 0) -> dict[str, object]:
    job_id = enqueue_job(create_demo_leads, count, interval_seconds)
    return {"job": "demo_leads", "job_id": job_id}


@router.post("/jobs/enqueue/enrichment")
def enqueue_enrichment() -> dict[str, object]:
    job_id = enqueue_job(process_pending_enrichment_jobs)
    return {"job": "enrichment", "job_id": job_id}


@router.post("/jobs/enqueue/enrichment-high-value")
def enqueue_high_value_enrichment() -> dict[str, object]:
    job_id = enqueue_job(process_pending_enrichment_jobs, 500)
    return {"job": "enrichment_high_value", "job_id": job_id}


@router.post("/jobs/enqueue/sync-google-sheets")
def enqueue_sync_google_sheets() -> dict[str, object]:
    job_id = enqueue_job(sync_google_sheets_job)
    return {"job": "sync_google_sheets", "job_id": job_id}


def _serialize_results(results: Mapping[str, GoogleSheetsSyncResult]) -> dict[str, object]:
    return {key: asdict(value) for key, value in results.items()}


def _database_ok(session: Session) -> bool:
    try:
        session.scalar(select(1))
        return True
    except Exception:
        return False


def _last_audit(session: Session, action: str) -> str | None:
    event = session.scalar(
        select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at.desc())
    )
    return event.created_at.isoformat() if event and event.created_at else None


def _last_ingestion_run(session: Session) -> dict[str, object] | None:
    run = session.scalar(select(IngestionRun).order_by(IngestionRun.started_at.desc()))
    if run is None:
        return None
    return {
        "batch_number": run.batch_number,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _last_enrichment_run(session: Session) -> dict[str, object] | None:
    run = session.scalar(select(EnrichmentRun).order_by(EnrichmentRun.started_at.desc()))
    if run is None:
        return None
    return {
        "enrichment_run_id": run.enrichment_run_id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _last_lead_inserted_at(session: Session) -> str | None:
    signal = session.scalar(select(LeadSignal).order_by(LeadSignal.created_at.desc()))
    return signal.created_at.isoformat() if signal and signal.created_at else None
