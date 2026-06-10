from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.integrations.google_sheets import GoogleSheetsSyncResult, GoogleSheetsSyncService
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


# TODO: Replace with authenticated admin authorization before production exposure.
@router.get("/sync/google-sheets/status")
def google_sheets_sync_status(session: SessionDependency) -> dict[str, object]:
    return asdict(GoogleSheetsSyncService(session).status())


@router.post("/sync/google-sheets/all")
def sync_google_sheets_all(session: SessionDependency) -> dict[str, object]:
    return _serialize_results(GoogleSheetsSyncService(session).sync_all_to_master_sheet())


@router.post("/sync/google-sheets/leads")
def sync_google_sheets_leads(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_new_leads_to_master_sheet()
    return asdict(result)


@router.post("/sync/google-sheets/batches")
def sync_google_sheets_batches(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_batch_log_to_master_sheet()
    return asdict(result)


@router.post("/sync/google-sheets/sources")
def sync_google_sheets_sources(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_sources_to_master_sheet()
    return asdict(result)


@router.post("/sync/google-sheets/deliveries")
def sync_google_sheets_deliveries(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_delivery_log_to_master_sheet()
    return asdict(result)


@router.post("/sync/google-sheets/opt-in-leads")
def sync_google_sheets_opt_in_leads(session: SessionDependency) -> dict[str, object]:
    result = GoogleSheetsSyncService(session).sync_opt_in_leads_to_master_sheet()
    return asdict(result)


def _serialize_results(results: Mapping[str, GoogleSheetsSyncResult]) -> dict[str, object]:
    return {key: asdict(value) for key, value in results.items()}
