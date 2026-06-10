from __future__ import annotations

import sys

from app.jobs.queue import make_worker
from app.jobs.tasks import record_worker_heartbeat


def main() -> None:
    try:
        record_worker_heartbeat()
        worker = make_worker()
    except ImportError as exc:
        print(f"RQ/Redis dependencies are not installed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
