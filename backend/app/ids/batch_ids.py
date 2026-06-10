from __future__ import annotations

import re
from datetime import date

from sqlalchemy.orm import Session

from app.ids.lead_ids import _next_sequence_value
from app.models import SequenceType


def next_batch_number(
    session: Session,
    scope: str,
    batch_date: date | None = None,
) -> str:
    sequence_date = batch_date or date.today()
    normalized_scope = _normalize_scope(scope)
    value = _next_sequence_value(
        session,
        sequence_type=SequenceType.BATCH,
        scope=normalized_scope,
        sequence_date=sequence_date,
    )
    return f"BATCH-{normalized_scope}-{sequence_date:%Y%m%d}-{value:03d}"


def _normalize_scope(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "", value.upper())
    return normalized or "ALL"
