from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from app.jobs.queue import enqueue_job
from app.jobs.tasks import (
    create_demo_leads,
    process_pending_enrichment_jobs,
    run_live_sources_job,
    sync_google_sheets_job,
)


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.job == "enrichment":
        job_id = enqueue_job(process_pending_enrichment_jobs)
    elif args.job == "sync_google_sheets":
        job_id = enqueue_job(sync_google_sheets_job)
    elif args.job == "demo_leads":
        job_id = enqueue_job(
            create_demo_leads,
            args.count,
            args.interval_seconds,
        )
    elif args.job == "live_sources":
        job_id = enqueue_job(run_live_sources_job, args.state)
    else:
        print(f"Unsupported job: {args.job}", file=sys.stderr)
        return 2
    print(f"Enqueued {args.job}: {job_id}")
    return 0


def main() -> None:
    raise SystemExit(run())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enqueue MCA Legal Signal Engine jobs.")
    parser.add_argument(
        "--job",
        required=True,
        choices=("enrichment", "sync_google_sheets", "demo_leads", "live_sources"),
    )
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--interval-seconds", type=int, default=0)
    parser.add_argument("--state", choices=("NY", "FL"))
    return parser


if __name__ == "__main__":
    main()
