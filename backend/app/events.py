from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from app.config import settings

SIGNAL_EVENTS_CHANNEL = "mca_signal_events"
_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
_recent_events: deque[dict[str, Any]] = deque(maxlen=200)


def publish_event(event_type: str, payload: dict[str, object]) -> dict[str, Any]:
    event = {
        "event_type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
    _recent_events.append(event)
    for subscriber in list(_subscribers):
        try:
            subscriber.put_nowait(event)
        except asyncio.QueueFull:
            _subscribers.discard(subscriber)
    _publish_redis(event)
    return event


def signal_event_payload(signal: Any) -> dict[str, object]:
    return {
        "lead_reference_id": signal.lead_reference_id,
        "batch_number": signal.batch_number,
        "grade": getattr(signal.grade, "value", signal.grade),
        "score": signal.score,
        "state": signal.state,
        "county": signal.county,
        "business_name": signal.business_name,
        "funder_name": signal.funder_name,
        "signal_type": getattr(signal.signal_type, "value", signal.signal_type),
        "status": getattr(signal.status, "value", signal.status),
        "created_at": signal.created_at.isoformat() if signal.created_at else None,
    }


def recent_events(limit: int = 20) -> list[dict[str, Any]]:
    return list(_recent_events)[-limit:]


async def event_stream() -> AsyncIterator[str]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    _subscribers.add(queue)
    try:
        yield _sse("connected", {"status": "connected"})
        for event in recent_events(20):
            yield _sse(event["event_type"], event)
        while True:
            event = await queue.get()
            yield _sse(event["event_type"], event)
    finally:
        _subscribers.discard(queue)


def _sse(event_type: str, payload: object) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


def _publish_redis(event: dict[str, Any]) -> None:
    try:
        from redis import Redis  # type: ignore[import-not-found]
    except ImportError:
        return
    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        redis.publish(SIGNAL_EVENTS_CHANNEL, json.dumps(event, default=str))
    except Exception:
        return
