from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from app.db import SessionLocal
from app.harvest.live_harvester import LiveHarvester


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    states = tuple(state.upper() for state in args.state)
    with SessionLocal() as session:
        result = LiveHarvester(session).run(
            states=states,
            target=args.target,
            dry_run=args.dry_run,
            enrich=not args.no_enrich,
            sync_google_sheets=args.sync_google_sheets,
            export=not args.no_export,
        )
    print(json.dumps(result.as_dict(), indent=2, default=str))
    return 0 if result.status in {"ok", "partial", "skipped"} else 1


def main() -> None:
    raise SystemExit(run())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run policy-gated live MCA source harvest.")
    parser.add_argument("--state", action="append", choices=("NY", "FL"), default=[])
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-enrich", action="store_true")
    parser.add_argument("--sync-google-sheets", action="store_true")
    parser.add_argument("--no-export", action="store_true")
    return parser


if __name__ == "__main__":
    main()
