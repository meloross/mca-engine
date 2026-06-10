from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session

from alembic import command
from app.db import SessionLocal
from app.models import LeadSignal, LeadSignalGrade
from app.services.presentation import analytics_summary


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    os.chdir(backend_dir)
    alembic_config = Config(str(backend_dir / "alembic.ini"))

    print("Resetting database...")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    print("Seeding demo data...")
    from app.jobs.seed_demo import seed_demo_data

    summary = asyncio.run(seed_demo_data())
    print(json.dumps(summary, indent=2, sort_keys=True))

    with SessionLocal() as session:
        print()
        print("Dashboard: http://localhost:8000/dashboard")
        print("API docs:   http://localhost:8000/docs")
        print()
        _print_top_signals(session, "NY")
        _print_top_signals(session, "FL")
        print()
        print("Analytics summary:")
        print(json.dumps(analytics_summary(session), indent=2, sort_keys=True, default=str))


def _print_top_signals(session: Session, state: str) -> None:
    signals = session.scalars(
        select(LeadSignal)
        .where(LeadSignal.state == state, LeadSignal.grade == LeadSignalGrade.A_PLUS)
        .order_by(LeadSignal.score.desc(), LeadSignal.signal_date.desc())
        .limit(5)
    ).all()
    print(f"Top A+ {state} signals:")
    if not signals:
        print("  No A+ signals found.")
        return
    for signal in signals:
        print(
            f"  {signal.score:3d} | {signal.business_name} | {signal.funder_name} | "
            f"{signal.county} | {signal.signal_date}"
        )


if __name__ == "__main__":
    main()
