from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from app.jobs.queue import enqueue_job
from app.jobs.tasks import (
    create_daily_batch_summary,
    export_daily_high_value_job,
    process_pending_enrichment_jobs,
    record_scheduler_heartbeat,
    refresh_analytics_dashboard_summary,
    run_live_sources_job,
    sync_google_sheets_job,
)


def main() -> None:
    schedule = {
        "enrichment": _due_now(),
        "sync": _due_now(),
        "analytics": _due_now(),
        "live_sources": _due_now(),
        "daily_export": _due_now(),
        "daily_summary": _due_now(),
    }
    while True:
        now = datetime.now(UTC)
        record_scheduler_heartbeat()
        if now >= schedule["enrichment"]:
            enqueue_job(process_pending_enrichment_jobs)
            schedule["enrichment"] = now + timedelta(minutes=5)
        if now >= schedule["sync"]:
            enqueue_job(sync_google_sheets_job)
            schedule["sync"] = now + timedelta(minutes=10)
        if now >= schedule["analytics"]:
            enqueue_job(refresh_analytics_dashboard_summary)
            schedule["analytics"] = now + timedelta(minutes=15)
        if now >= schedule["live_sources"]:
            enqueue_job(run_live_sources_job)
            schedule["live_sources"] = now + timedelta(minutes=30)
        if now >= schedule["daily_export"]:
            enqueue_job(export_daily_high_value_job)
            schedule["daily_export"] = now + timedelta(days=1)
        if now >= schedule["daily_summary"]:
            enqueue_job(create_daily_batch_summary)
            schedule["daily_summary"] = now + timedelta(days=1)
        time.sleep(30)


def _due_now() -> datetime:
    return datetime.now(UTC)


if __name__ == "__main__":
    main()
