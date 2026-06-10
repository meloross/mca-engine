from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.fl_importer import import_mock_fl_to_db
from app.services.ny_importer import import_mock_ny_to_db

router = APIRouter(prefix="/admin", tags=["admin"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/import/mock")
async def import_mock(
    state: Annotated[str, Query(min_length=2, max_length=2)],
    session: SessionDependency,
) -> dict[str, int | str]:
    normalized_state = state.upper()
    if normalized_state == "NY":
        result = await import_mock_ny_to_db(session)
        return {"state": "NY", **result}
    if normalized_state == "FL":
        result = await import_mock_fl_to_db(session)
        return {"state": "FL", **result}

    raise HTTPException(status_code=400, detail="Only NY and FL mock imports are implemented.")
