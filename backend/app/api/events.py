from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.events import event_stream

router = APIRouter(tags=["events"])


@router.get("/events/signals")
async def stream_signal_events() -> StreamingResponse:
    return StreamingResponse(event_stream(), media_type="text/event-stream")
