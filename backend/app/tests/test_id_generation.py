from __future__ import annotations

from datetime import date
from typing import Any, cast

from sqlalchemy.orm import Session

from app.ids import (
    next_batch_number,
    next_delivery_id,
    next_form_lead_ref_id,
    next_lead_reference_id,
)
from app.models import IdSequence, SequenceType


def test_batch_numbers_increment_by_scope_and_date() -> None:
    session = cast(Session, _FakeSequenceSession())
    sequence_date = date(2026, 6, 10)

    assert next_batch_number(session, "NY", sequence_date) == "BATCH-NY-20260610-001"
    assert next_batch_number(session, "NY", sequence_date) == "BATCH-NY-20260610-002"
    assert next_batch_number(session, "FL", sequence_date) == "BATCH-FL-20260610-001"


def test_lead_reference_ids_increment_per_state_and_date() -> None:
    session = cast(Session, _FakeSequenceSession())
    sequence_date = date(2026, 6, 10)

    assert next_lead_reference_id(session, "NY", sequence_date) == "MCA-NY-20260610-000001"
    assert next_lead_reference_id(session, "NY", sequence_date) == "MCA-NY-20260610-000002"
    assert next_lead_reference_id(session, "FL", sequence_date) == "MCA-FL-20260610-000001"


def test_form_and_delivery_ids_increment_without_duplicates() -> None:
    session = cast(Session, _FakeSequenceSession())
    sequence_date = date(2026, 6, 10)

    form_ids = {next_form_lead_ref_id(session, sequence_date) for _ in range(3)}
    delivery_ids = {next_delivery_id(session, sequence_date) for _ in range(3)}

    assert form_ids == {
        "FORM-MCA-20260610-000001",
        "FORM-MCA-20260610-000002",
        "FORM-MCA-20260610-000003",
    }
    assert delivery_ids == {
        "DLV-20260610-000001",
        "DLV-20260610-000002",
        "DLV-20260610-000003",
    }


class _FakeSequenceSession:
    def __init__(self) -> None:
        self.sequences: dict[tuple[SequenceType, str, str], IdSequence] = {}

    def scalar(self, statement: object) -> IdSequence | None:
        key = self._key_from_statement(statement)
        return self.sequences.get(key)

    def add(self, value: object) -> None:
        if isinstance(value, IdSequence):
            self.sequences[(value.sequence_type, value.scope, value.date_key)] = value

    def flush(self) -> None:
        return None

    def _key_from_statement(self, statement: object) -> tuple[SequenceType, str, str]:
        values: dict[str, Any] = {}
        for criterion in getattr(statement, "_where_criteria", ()):
            column_name = str(getattr(criterion, "left", "")).split(".")[-1]
            values[column_name] = getattr(getattr(criterion, "right", None), "value", None)
        return (
            SequenceType(values["sequence_type"]),
            str(values["scope"]),
            str(values["date_key"]),
        )
