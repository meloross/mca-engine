from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classifiers.funder_matcher import SEED_MCA_FUNDERS
from app.models import McaFunder


def load_funder_queries(session: Session, *, limit: int = 50) -> list[str]:
    names = [
        funder.name
        for funder in session.scalars(
            select(McaFunder).where(McaFunder.active.is_(True)).order_by(McaFunder.name).limit(limit)
        ).all()
    ]
    if names:
        return names
    return list(SEED_MCA_FUNDERS[:limit])
