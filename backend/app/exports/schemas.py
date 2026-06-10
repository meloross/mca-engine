from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

ExportFormat = Literal["csv", "xlsx"]
ExportType = Literal["signals", "form-leads"]


@dataclass(frozen=True)
class ExportFilters:
    states: tuple[str, ...] = ()
    county: str | None = None
    grade: str | None = None
    min_score: int | None = None
    signal_type: str | None = None
    funder_name: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    status: str | None = None
    only_high_value: bool = False
    include_suppressed: bool = False
    include_excluded: bool = False

    @classmethod
    def from_state(
        cls,
        *,
        state: str | None = None,
        states: list[str] | tuple[str, ...] | None = None,
        county: str | None = None,
        grade: str | None = None,
        min_score: int | None = None,
        signal_type: str | None = None,
        funder_name: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        status: str | None = None,
        only_high_value: bool = False,
        include_suppressed: bool = False,
        include_excluded: bool = False,
    ) -> ExportFilters:
        supplied_states = tuple(state.upper() for state in (states or ()) if state)
        if state:
            supplied_states = (*supplied_states, state.upper())
        return cls(
            states=tuple(dict.fromkeys(supplied_states)),
            county=county,
            grade=grade,
            min_score=min_score,
            signal_type=signal_type,
            funder_name=funder_name,
            date_from=date_from,
            date_to=date_to,
            status=status,
            only_high_value=only_high_value,
            include_suppressed=include_suppressed,
            include_excluded=include_excluded,
        )

    def as_metadata(self) -> dict[str, object]:
        return {
            "states": ", ".join(self.states) or "ALL",
            "county": self.county or "",
            "grade": self.grade or "",
            "min_score": self.min_score if self.min_score is not None else "",
            "signal_type": self.signal_type or "",
            "funder_name": self.funder_name or "",
            "date_from": self.date_from.isoformat() if self.date_from else "",
            "date_to": self.date_to.isoformat() if self.date_to else "",
            "status": self.status or "",
            "only_high_value": self.only_high_value,
            "include_suppressed": self.include_suppressed,
            "include_excluded": self.include_excluded,
        }


@dataclass(frozen=True)
class ExportResult:
    content: bytes
    filename: str
    media_type: str
    row_count: int
    export_timestamp: datetime
    filters: ExportFilters
    omitted_counts: dict[str, int] = field(default_factory=dict)
