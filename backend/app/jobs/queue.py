from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.config import settings

DEFAULT_QUEUE = "mca-default"


@dataclass(frozen=True)
class QueueStatus:
    queue_name: str
    pending_jobs: int
    failed_jobs: int
    redis_connected: bool


def enqueue_job(func: Callable[..., object], *args: object, **kwargs: object) -> str:
    try:
        from redis import Redis  # type: ignore[import-not-found]
        from rq import Queue  # type: ignore[import-not-found]
    except ImportError:
        func(*args, **kwargs)
        return "inline"

    redis = Redis.from_url(settings.redis_url)
    queue = Queue(DEFAULT_QUEUE, connection=redis)
    job = queue.enqueue(func, *args, **kwargs)
    return str(job.id)


def queue_status() -> QueueStatus:
    try:
        from redis import Redis
        from rq import Queue
        from rq.registry import FailedJobRegistry  # type: ignore[import-not-found]
    except ImportError:
        return QueueStatus(DEFAULT_QUEUE, 0, 0, False)

    try:
        redis = Redis.from_url(settings.redis_url)
        redis.ping()
        queue = Queue(DEFAULT_QUEUE, connection=redis)
        failed = FailedJobRegistry(queue=queue)
        return QueueStatus(DEFAULT_QUEUE, len(queue), len(failed), True)
    except Exception:
        return QueueStatus(DEFAULT_QUEUE, 0, 0, False)


def make_worker() -> Any:
    from redis import Redis
    from rq import Queue, Worker

    redis = Redis.from_url(settings.redis_url)
    queue = Queue(DEFAULT_QUEUE, connection=redis)
    return Worker([queue], connection=redis)
