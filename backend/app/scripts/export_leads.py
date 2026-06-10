from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.exports import ExportFilters, export_form_leads_bytes, export_signals_bytes
from app.exports.schemas import ExportFormat, ExportType

SessionFactory = Callable[[], AbstractContextManager[Session]]


def run(
    argv: Sequence[str] | None = None,
    *,
    session_factory: SessionFactory = SessionLocal,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    export_type: ExportType = args.type
    export_format: ExportFormat = args.format
    output_path = Path(args.output)
    filters = ExportFilters.from_state(
        state=args.state,
        states=tuple(args.states or ()),
        county=args.county,
        grade=args.grade,
        min_score=args.min_score,
        signal_type=args.signal_type,
        funder_name=args.funder_name,
        date_from=_parse_date(args.date_from),
        date_to=_parse_date(args.date_to),
        status=args.status,
        only_high_value=args.only_high_value,
        include_suppressed=args.include_suppressed,
        include_excluded=args.include_excluded,
    )

    _validate_output(output_path, export_format)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with session_factory() as session:
        result = (
            export_signals_bytes(session, filters=filters, export_format=export_format)
            if export_type == "signals"
            else export_form_leads_bytes(session, filters=filters, export_format=export_format)
        )
    output_path.write_bytes(result.content)
    print(f"Exported {result.row_count} rows")
    print(f"Output: {output_path.resolve()}")
    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export MCA legal leads to CSV or XLSX.")
    parser.add_argument("--type", choices=("signals", "form-leads"), required=True)
    parser.add_argument("--format", choices=("csv", "xlsx"), required=True)
    parser.add_argument("--state", help="Single state filter, e.g. NY")
    parser.add_argument("--states", nargs="+", help="Multiple state filters, e.g. NY FL")
    parser.add_argument("--county")
    parser.add_argument("--grade")
    parser.add_argument("--min-score", type=int)
    parser.add_argument("--signal-type")
    parser.add_argument("--funder-name")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--status")
    parser.add_argument("--only-high-value", action="store_true")
    parser.add_argument("--include-suppressed", action="store_true")
    parser.add_argument("--include-excluded", action="store_true")
    parser.add_argument("--output", required=True)
    return parser


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _validate_output(path: Path, export_format: ExportFormat) -> None:
    expected_suffix = f".{export_format}"
    if path.suffix.lower() != expected_suffix:
        raise ValueError(f"Output path must end in {expected_suffix}")


if __name__ == "__main__":
    main()
