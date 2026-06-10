from __future__ import annotations

import json
from typing import Any, Protocol, cast

from app.config import settings

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
MASTER_SHEET_URL = "https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


class SheetsServiceProtocol(Protocol):
    def spreadsheets(self) -> Any: ...


class GoogleSheetsClient:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        spreadsheet_id: str | None = None,
        service: SheetsServiceProtocol | None = None,
    ) -> None:
        self.enabled = settings.google_sheets_enabled if enabled is None else enabled
        self.spreadsheet_id = spreadsheet_id or settings.mca_master_spreadsheet_id
        self._service = service

    @property
    def sheet_url(self) -> str:
        return MASTER_SHEET_URL.format(spreadsheet_id=self.spreadsheet_id)

    def get_column_values(self, tab_name: str, column: str = "A") -> list[str]:
        if not self.enabled:
            return []
        range_name = f"{tab_name}!{column}:{column}"
        response = (
            self._sheets()
            .spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_name)
            .execute()
        )
        values = response.get("values", [])
        return [str(row[0]) for row in values if row]

    def append_rows(self, tab_name: str, rows: list[list[str]]) -> dict[str, Any]:
        if not self.enabled or not rows:
            return {"updates": {"updatedRows": 0}}
        range_name = f"{tab_name}!A:A"
        response = (
            self._sheets()
            .spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            )
            .execute()
        )
        return cast(dict[str, Any], response)

    def update_row(self, tab_name: str, row_number: int, row: list[str]) -> dict[str, Any]:
        if not self.enabled:
            return {"updatedRows": 0}
        range_name = f"{tab_name}!A{row_number}:BF{row_number}"
        response = (
            self._sheets()
            .spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": [row]},
            )
            .execute()
        )
        return cast(dict[str, Any], response)

    def _sheets(self) -> SheetsServiceProtocol:
        if self._service is None:
            self._service = _build_service()
        return self._service


def _build_service() -> SheetsServiceProtocol:
    from google.oauth2 import service_account  # type: ignore[import-not-found]
    from googleapiclient.discovery import build  # type: ignore[import-not-found]

    if settings.google_service_account_json:
        info = json.loads(settings.google_service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=[SHEETS_SCOPE],
        )
    elif settings.google_application_credentials:
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_application_credentials,
            scopes=[SHEETS_SCOPE],
        )
    else:
        raise RuntimeError(
            "Google Sheets sync is enabled but no service account credentials are configured."
        )
    return cast(
        SheetsServiceProtocol,
        build("sheets", "v4", credentials=credentials, cache_discovery=False),
    )
