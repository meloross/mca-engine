from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import asdict

from app.db import SessionLocal
from app.integrations.google_sheets import GoogleSheetsSyncResult, GoogleSheetsSyncService


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    with SessionLocal() as session:
        service = GoogleSheetsSyncService(session)
        status = service.status()
        print(f"Google Sheets enabled: {status.enabled}")
        print(f"Spreadsheet: https://docs.google.com/spreadsheets/d/{status.spreadsheet_id}/edit")
        print(f"Unsynced leads: {status.unsynced_leads_count}")
        print(f"Unsynced batches: {status.unsynced_batches_count}")
        print(f"Unsynced deliveries: {status.unsynced_deliveries_count}")
        print(f"Unsynced opt-in leads: {status.unsynced_opt_in_leads_count}")

        if args.status:
            return 0

        results: dict[str, GoogleSheetsSyncResult] = {}
        if args.all:
            results = service.sync_all_to_master_sheet()
        else:
            if args.leads:
                results["leads"] = service.sync_new_leads_to_master_sheet()
            if args.batches:
                results["batches"] = service.sync_batch_log_to_master_sheet()
            if args.opt_in_leads:
                results["opt_in_leads"] = service.sync_opt_in_leads_to_master_sheet()

        if not results:
            print(
                "No sync target selected. Use --status, --all, --leads, "
                "--batches, or --opt-in-leads."
            )
            return 2

        has_error = False
        for name, result in results.items():
            print(
                f"{name}: attempted={result.attempted} appended={result.appended} "
                f"duplicates={result.skipped_duplicates} enabled={result.enabled}"
            )
            if result.error:
                has_error = True
                print(f"{name} error: {result.error}", file=sys.stderr)
            else:
                print(asdict(result))
        return 1 if has_error else 0


def main() -> None:
    raise SystemExit(run())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync MCA tracker data to Google Sheets.")
    parser.add_argument("--all", action="store_true", help="Sync every supported sheet tab.")
    parser.add_argument("--leads", action="store_true", help="Sync Lead_Master rows.")
    parser.add_argument("--batches", action="store_true", help="Sync Batch_Log rows.")
    parser.add_argument("--opt-in-leads", action="store_true", help="Sync Opt_In_Leads rows.")
    parser.add_argument("--status", action="store_true", help="Print sync status only.")
    return parser


if __name__ == "__main__":
    main()
