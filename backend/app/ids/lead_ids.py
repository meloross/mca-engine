from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IdSequence, SequenceType


def next_lead_reference_id(
    session: Session,
    state: str,
    signal_date: date | None = None,
) -> str:
    sequence_date = signal_date or date.today()
    scope = _normalize_scope(state)
    value = _next_sequence_value(
        session,
        sequence_type=SequenceType.LEAD_REFERENCE,
        scope=scope,
        sequence_date=sequence_date,
    )
    return f"MCA-{scope}-{_date_key(sequence_date)}-{value:06d}"


def next_form_lead_ref_id(session: Session, created_date: date | None = None) -> str:
    sequence_date = created_date or date.today()
    value = _next_sequence_value(
        session,
        sequence_type=SequenceType.FORM_LEAD,
        scope="MCA",
        sequence_date=sequence_date,
    )
    return f"FORM-MCA-{_date_key(sequence_date)}-{value:06d}"


def next_delivery_id(session: Session, delivery_date: date | None = None) -> str:
    sequence_date = delivery_date or date.today()
    value = _next_sequence_value(
        session,
        sequence_type=SequenceType.DELIVERY,
        scope="ALL",
        sequence_date=sequence_date,
    )
    return f"DLV-{_date_key(sequence_date)}-{value:06d}"


def _next_sequence_value(
    session: Session,
    *,
    sequence_type: SequenceType,
    scope: str,
    sequence_date: date,
) -> int:
    date_key = _date_key(sequence_date)
    statement = (
        select(IdSequence)
        .where(
            IdSequence.sequence_type == sequence_type,
            IdSequence.scope == scope,
            IdSequence.date_key == date_key,
        )
        .with_for_update()
    )
    sequence = session.scalar(statement)
    if sequence is None:
        sequence = IdSequence(
            sequence_type=sequence_type,
            scope=scope,
            date_key=date_key,
            current_value=0,
        )
        session.add(sequence)
        session.flush()

    sequence.current_value += 1
    session.add(sequence)
    session.flush()
    return sequence.current_value


def _date_key(value: date) -> str:
    return value.strftime("%Y%m%d")


def _normalize_scope(value: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "", value.upper())
    return normalized or "ALL"
